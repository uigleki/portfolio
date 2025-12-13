# %%
import os
import time
from collections import deque
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import List, Tuple, TypeVar

import cv2
import numpy as np
import pandas as pd
import pytesseract  # type: ignore[import-untyped]

IS_KAGGLE = bool(os.getenv("KAGGLE_KERNEL_RUN_TYPE"))
INPUT_DIR = (
    Path("../input/trades") if IS_KAGGLE else Path(__file__).parent / "../raw_data"
)
OUTPUT_DIR = Path() if IS_KAGGLE else INPUT_DIR
TESS_DIR = (
    "" if IS_KAGGLE else f"--tessdata-dir '{Path(__file__).parent / '../tessdata'}'"
)

TABLE_RANGE = (346, 658, 35, 764)
Y_RANGES = [
    (1, 19),
    (21, 39),
    (40, 58),
    (60, 78),
    (79, 97),
    (99, 117),
    (118, 136),
    (138, 156),
    (157, 175),
    (177, 195),
    (196, 214),
    (216, 234),
    (235, 253),
    (255, 273),
    (274, 292),
    (294, 312),
]

T = TypeVar("T")


def unwrap(x: T | None) -> T:
    assert x is not None
    return x


def gray_region(img: np.ndarray, region: Tuple[int, int, int, int]) -> np.ndarray:
    y1, y2, x1, x2 = region
    return cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)


class OCR:
    # Character whitelists for different OCR modes
    CHARS = {
        "int": "0123456789",
        "dt": "0123456789.:",
        "time": "0123456789:",
        "type": "buysell",
        "abc": "abcdefghijklmnopqrstuvwxyz",
        "dec": "0123456789.",
    }
    # Common OCR misrecognitions to fix
    CORRECTIONS = {
        "buy": "buy ",
        "auusd": "xauusd",
        "yauusd": "xauusd",
        "usdead": "usdcad",
        "14.00": "1.00",
    }

    @staticmethod
    def _format_datetime(text: str) -> str:
        """Convert OCR result like '20230815143025' to '2023-08-15 14:30:25'"""
        digits = "".join(filter(str.isdigit, text))

        if len(digits) != 14:
            print(f"錯誤：格式異常。原始字串：{text}")
            return text

        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]} {digits[8:10]}:{digits[10:12]}:{digits[12:14]}"

    @classmethod
    def read(cls, img: np.ndarray, mode: str = "dec") -> str:
        config = f"{TESS_DIR} --psm 7 -c tessedit_char_whitelist={cls.CHARS[mode]}"
        text = pytesseract.image_to_string(img, config=config).strip().strip(".")

        if mode == "dt":
            text = cls._format_datetime(text)
        elif mode == "dec" and text.startswith("4."):
            # Fix common OCR error: "1.2345" misread as "4.2345"
            text = "1." + text[2:]

        return cls.CORRECTIONS.get(text, text)


class FrameReader:
    TIME_RANGE = (55, 68, 80, 135)
    X_RANGES = [
        (0, 65),
        (110, 222),
        (265, 292),
        (315, 347),
        (365, 417),
        (440, 495),
        (675, 729),
    ]
    COL_MODES = ["dt", "type", "dec", "abc", "dec"]

    def __init__(self, frame: np.ndarray):
        self.frame = frame
        self.table = gray_region(frame, TABLE_RANGE)

    @staticmethod
    def _ocr_region(
        img: np.ndarray, region: Tuple[int, int, int, int], mode: str
    ) -> str:
        y1, y2, x1, x2 = region
        roi = img[y1:y2, x1:x2]
        return OCR.read(roi, mode)

    def _read_cell(self, row: int, col: int, mode: str) -> str:
        return self._ocr_region(self.table, (*Y_RANGES[row], *self.X_RANGES[col]), mode)

    def get_id(self, row: int) -> str:
        return self._read_cell(row, 0, "int")

    def get_row_data(self, row: int) -> List[str]:
        return [
            self._read_cell(row, col, mode)
            for col, mode in enumerate(self.COL_MODES, start=1)
        ]

    def get_price(self, row: int) -> str:
        return self._read_cell(row, 6, "dec")

    @cached_property
    def timestamp(self) -> str:
        return OCR.read(gray_region(self.frame, self.TIME_RANGE), "time")


class Shot:
    y1, y2, _, _ = TABLE_RANGE
    BAR_RANGE = (y1, y2, 1060, 1063)
    ID_RANGE = (y1, y2, 62, 96)
    BAR_ROW_RANGES = [(y1 + 7, y2 - 7) for y1, y2 in Y_RANGES]
    ID_ROW_RANGES = [(y1 + 3, y2 - 3) for y1, y2 in Y_RANGES]

    def __init__(self, frame: np.ndarray):
        self.frame = frame
        self.id_img = gray_region(frame, self.ID_RANGE)
        self.bar = self._locate_bar()

    @staticmethod
    def _compare_images(img1: np.ndarray, img2: np.ndarray, thresh: float = 5) -> bool:
        return bool(np.mean(cv2.absdiff(img1, img2)) < thresh)

    def _locate_bar(self) -> int:
        """Find the scroll bar position (which row the cursor is at)"""
        bar_img = gray_region(self.frame, self.BAR_RANGE)
        return next(
            (
                len(Y_RANGES) - 1 - i
                for i, (y1, y2) in enumerate(reversed(self.BAR_ROW_RANGES))
                if abs(np.mean(bar_img[y1:y2]) - 200) < 10
            ),
            -1,
        )

    def is_similar(self, other: "Shot") -> bool:
        if not isinstance(other, Shot) or self.bar < 0 or self.bar != other.bar:
            return False
        return all(
            self._compare_images(self.id_img[y1:y2], other.id_img[y1:y2])
            for y1, y2 in reversed(self.ID_ROW_RANGES[: self.bar])
        )

    def change_range(self, other: "Shot") -> Tuple[int, int]:
        start = next(
            (
                i
                for i, (y1, y2) in enumerate(self.ID_ROW_RANGES[: other.bar])
                if not self._compare_images(self.id_img[y1:y2], other.id_img[y1:y2])
            ),
            0,
        )
        return start, other.bar


class VideoAnalyzer:
    def __init__(self, path: str, start_pos: int = 0):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise ValueError("無法開啟影片檔案")
        self.frame_pos = start_pos
        self._set_pos(start_pos)
        self.last_shot = unwrap(self._read_shot())
        self.STEP_SIZE = int(self.cap.get(cv2.CAP_PROP_FPS))

    def __del__(self):
        self.cap.release()

    def _set_pos(self, pos: int):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, pos)

    def _read_shot(self) -> Shot | None:
        ret, frame = self.cap.read()
        return Shot(frame) if ret else None

    def _compare_shot(self, other: Shot | None = None) -> Tuple[Shot | None, bool]:
        other = other or self.last_shot
        shot = self._read_shot()
        same = shot is not None and other.is_similar(shot)
        return shot, same

    def _find_transition(self) -> int:
        """Fast-forward to find frame where table content changes"""
        while True:
            self.frame_pos += self.STEP_SIZE
            self._set_pos(self.frame_pos)
            if not self._compare_shot()[1]:
                self.frame_pos -= self.STEP_SIZE
                self._set_pos(self.frame_pos)
                return self.frame_pos

    def _find_pre_change(self) -> Shot:
        shots = deque([self.last_shot], 2)
        while True:
            shot, same = self._compare_shot()
            if not same:
                return shots[0]
            shots.append(unwrap(shot))

    def _find_post_change(self) -> Shot | None:
        """Find stable frame after table change (skip animation frames)"""
        if (last_shot := self._read_shot()) is None:
            return None
        count = 0
        while shot := self._read_shot():
            if last_shot.is_similar(shot):
                count += 1
                if count > 1:
                    self.frame_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                    self.last_shot = shot
                    return shot
            else:
                count = 0
                last_shot = shot
        return None

    def init_frame(self) -> Tuple[np.ndarray, int]:
        return self.last_shot.frame, self.last_shot.bar

    def next_change(self) -> Tuple[np.ndarray, np.ndarray | None, Tuple[int, int], int]:
        save_pos = self._find_transition()
        pre_shot = self._find_pre_change()
        post_shot = self._find_post_change()
        if post_shot is None:
            return pre_shot.frame, None, (-1, -1), save_pos
        return (
            pre_shot.frame,
            post_shot.frame,
            pre_shot.change_range(post_shot),
            save_pos,
        )


class TradeDataProcessor:
    COLUMNS = [
        "Order",
        "Time",
        "Type",
        "Size",
        "Symbol",
        "Price",
        "End Time",
        "End Price",
        "frame_pos",
    ]
    END_PRICE_COL_INDEX = COLUMNS.index("End Price")

    def __init__(self, video_path: str, resume_data: bool = True):
        name = Path(video_path).stem
        self.OUT_PATH = Path(OUTPUT_DIR / f"{name}.csv")
        self.RAW_PATH = Path(OUTPUT_DIR / f"{name}_raw.csv")
        self.df, self.frame_pos = self._load_data(resume_data)
        self.va = VideoAnalyzer(video_path, self.frame_pos)
        frame, count = self.va.init_frame()
        self.proc = FrameReader(frame)
        self.pos = [self.proc.get_id(i) for i in range(count)] if self.proc else []
        self.prev_proc = self.proc

    def _load_data(self, resume_data: bool = True) -> Tuple[pd.DataFrame, int]:
        frame_pos = 0
        if resume_data and self.RAW_PATH.is_file():
            df = pd.read_csv(self.RAW_PATH, dtype=str).fillna("")
            frame_pos = int(df["frame_pos"].iloc[-1])
            print(f"從幀位置繼續：{frame_pos}")
        else:
            df = pd.DataFrame(columns=self.COLUMNS)
        return df.set_index("Order"), frame_pos

    def _get_change(self) -> List[str] | None:
        """Extract changed order IDs from video frames, handling OCR duplicates"""
        prev_frame, frame, (start, end), self.frame_pos = self.va.next_change()
        if frame is None:
            return None

        self.prev_proc, self.proc = FrameReader(prev_frame), FrameReader(frame)

        while True:
            change = [self.proc.get_id(i) for i in range(start, end)]
            # If no duplicate IDs, accept this result
            if len(change) == len(set(change)):
                return self.pos[:start] + change

            # OCR duplicates detected, try next frame
            _, next_frame, (next_start, end), _ = self.va.next_change()
            if next_frame is None:
                return None

            self.proc = FrameReader(next_frame)
            start = min(start, next_start)

    def _print_row(self, idx: str):
        values = self.df.loc[idx].iloc[: self.END_PRICE_COL_INDEX]
        print(idx, *values, sep="  ")

    def _update_positions(self, prev: List[str], curr: List[str]):
        for idx in [i for i in prev if i not in curr]:
            self.df.loc[idx, ["End Time", "End Price"]] = [
                self.prev_proc.timestamp,
                self.prev_proc.get_price(prev.index(idx)),
            ]
            self._print_row(idx)

        for idx in [i for i in curr if i not in prev]:
            if idx not in self.df.index:
                self.df.loc[idx] = self.proc.get_row_data(curr.index(idx)) + [
                    "",
                    "",
                    self.frame_pos,
                ]
                self._print_row(idx)

        self.save_output(self.RAW_PATH)

    def _check_data(self) -> bool:
        print("類型：", list(self.df["Type"].unique()))
        print("商品：", list(self.df["Symbol"].unique()))

        price = pd.to_numeric(self.df["Price"], errors="coerce")
        end_price = pd.to_numeric(self.df["End Price"], errors="coerce")

        high = price > 10000
        valid = end_price.notna()
        diff = np.abs(price - end_price) / np.minimum(price, end_price)
        changed = diff > 0.01

        mask = high | (valid & changed)
        errors = self.df[mask]
        if not errors.empty:
            print("價格錯誤：")
            for idx in errors.index:
                self._print_row(idx)

        def is_valid_time(time_str: str | float) -> bool:
            if not isinstance(time_str, str):
                return False
            try:
                datetime.strptime(time_str, "%H:%M:%S")
                return True
            except ValueError:
                return False

        time_mask = valid & ~self.df["End Time"].apply(is_valid_time)
        time_errors = self.df[time_mask]
        if not time_errors.empty:
            print("時間格式錯誤：")
            for idx in time_errors.index:
                self._print_row(idx)
            return False
        return True

    def _correct_end_times(self):
        """Fix date for end times since OCR only captures HH:MM:SS (no date)"""
        self.df["Time"] = pd.to_datetime(self.df["Time"], format="ISO8601")
        self.df["End Time"] = pd.to_datetime(
            self.df["End Time"], format="%H:%M:%S"
        ).dt.time

        last_time = self.df["Time"].iloc[-1]

        grouped = self.df.groupby(["Symbol", "Type"])
        for _, group in grouped:
            group = group.sort_index()
            group_len = len(group)

            for i in range(group_len):
                if pd.notna(group.iloc[i]["End Time"]):
                    end_time = group.iloc[i]["End Time"]
                    current_time = group.iloc[i]["Time"]

                    next_time = (
                        last_time if i == group_len - 1 else group.iloc[i + 1]["Time"]
                    )

                    corrected_end_time = datetime.combine(next_time.date(), end_time)

                    # Handle day boundary crossings
                    if corrected_end_time > next_time:
                        corrected_end_time -= timedelta(days=1)
                    if corrected_end_time < current_time:
                        corrected_end_time += timedelta(days=1)

                    self.df.at[group.index[i], "End Time"] = corrected_end_time

    def process(self):
        start_time = time.time()
        self._update_positions([], self.pos)

        while new_pos := self._get_change():
            self._update_positions(self.pos, new_pos)
            self.pos = new_pos

        elapsed = int(time.time() - start_time)
        print(f"執行時間：{time.strftime('%H:%M:%S', time.gmtime(elapsed))}")

        if self._check_data():
            self._correct_end_times()

    def save_output(self, out_path: Path | str | None = None):
        out_path = out_path or self.OUT_PATH
        self.df.to_csv(out_path, lineterminator="\n")


# %%

if __name__ == "__main__":
    import sys

    processor = TradeDataProcessor(sys.argv[1])
    processor.process()
    processor.save_output()
