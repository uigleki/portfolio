using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Indicators;

namespace cAlgo.Robots
{
    public enum Preset
    {
        XAUUSD, USDJPY, GBPUSD, EURUSD,
        Custom
    }

    public static class Constants
    {
        public const string BotId = "RangeBreakoutBot";
    }

    // Asian session range breakout strategy with preset configurations
    [Robot(TimeZone = TimeZones.EasternStandardTime, AccessRights = AccessRights.None, AddIndicators = true)]
    public class RangeBreakoutBot : Robot
    {
        private const string GroupRisk = "Risk";
        private const string GroupTime = "MT5 Time (HHmm)";  // Display in MT5 timezone for clarity
        private const string GroupStopLoss = "Stop Loss";
        private const string GroupFilter = "Filter";
        private const string GroupColor = "Color";

        [Parameter("Risk %", DefaultValue = 0.5, Group = GroupRisk, MaxValue = 10, MinValue = 0, Step = 0.5)]
        public double RiskPct { get; set; }

        [Parameter("Equity Target (0 = off)", DefaultValue = 0, Group = GroupRisk, MinValue = 0, Step = 1000)]
        public double EquityTarget { get; set; }

        [Parameter("Preset (Custom for manual)", DefaultValue = Preset.XAUUSD, Group = GroupRisk)]
        public Preset ActivePreset { get; set; }

        [Parameter("Range Start", DefaultValue = 0305, Group = GroupTime, MaxValue = 2359, MinValue = 0, Step = 100)]
        public int StartTime { get; set; }

        [Parameter("Range End", DefaultValue = 0605, Group = GroupTime, MaxValue = 2359, MinValue = 0, Step = 100)]
        public int EndTime { get; set; }

        [Parameter("Close Positions", DefaultValue = 1855, Group = GroupTime, MaxValue = 2359, MinValue = 0, Step = 100)]
        public int CloseTime { get; set; }

        [Parameter("Stop Loss %", DefaultValue = 1, Group = GroupStopLoss, MaxValue = 5, MinValue = 0, Step = 0.5)]
        public double StopLossPct { get; set; }

        [Parameter("Min Range %", DefaultValue = 0.15, Group = GroupFilter, MaxValue = 5, MinValue = 0, Step = 0.05)]
        public double MinRangePct { get; set; }

        [Parameter("Max Range %", DefaultValue = 0.85, Group = GroupFilter, MaxValue = 5, MinValue = 0, Step = 0.05)]
        public double MaxRangePct { get; set; }

        [Parameter("Trade Both Side", DefaultValue = false, Group = GroupFilter)]
        public bool BothSide { get; set; }

        [Parameter("Range", DefaultValue = "SkyBlue", Group = GroupColor)]
        public Color RangeColor { get; set; }

        private TimeSpan _startTime, _endTime;
        private TimeSpan _closeTime;

        private int _botState = 0;  // 0 = waiting, 1 = active
        private double _highPrice;
        private double _lowPrice;
        private Bars _minBars;  // 1-minute bars for range calculation

        private static readonly Dictionary<Preset, Params> Presets = new()
        {
            [Preset.XAUUSD] = new(0305, 0605, 1855, 1, 0.15, 0.85),
            [Preset.USDJPY] = new(0300, 0430, 1800, 0.5, 0.2, 0.4),
            [Preset.GBPUSD] = new(0400, 1130, 1800, 0.5, 0.15, 0.4),
            [Preset.EURUSD] = new(0100, 0200, 1800, 1, 0.1, 0.6),
        };

        protected override void OnStart()
        {
            ApplyPreset(ActivePreset);
            _startTime = StartTime.ToTimeSpan().MtToEst();
            _endTime = EndTime.ToTimeSpan().MtToEst();
            _closeTime = CloseTime.ToTimeSpan().MtToEst();
            _minBars = MarketData.GetBars(TimeFrame.Minute);
        }

        protected override void OnTick()
        {
            // Stop bot when equity target reached
            if (EquityTarget != 0 && Account.Equity > EquityTarget)
            {
                this.CancelOrders();
                this.ClosePositions();
                Stop();
            }

            // Active trading window: after range formation until close time
            if (Server.Time.TimeOfDay.IsInRange(_endTime, _closeTime))
            {
                if (_botState == 0)
                {
                    _botState = 1;
                    SetupBreakoutOrders();
                }

                // Cancel opposite order when one side fills (if not trading both sides)
                if (!BothSide && Positions.Any(x => x.Label == Constants.BotId && x.SymbolName == SymbolName))
                    this.CancelOrders();
            }
            else
            {
                // Outside trading window: clean up and wait
                if (_botState == 1)
                {
                    _botState = 0;
                    this.CancelOrders();
                    this.ClosePositions();
                }
            }
        }

        protected override void OnBar()
        {
            base.OnBar();
        }

        protected override void OnStop()
        {
            base.OnStop();
        }

        private void SetupBreakoutOrders()
        {
            FindHighLow();
            var close = Bars.LastBar.Close;
            var span = (_highPrice - _lowPrice) / close;

            // Skip if range too narrow (choppy) or too wide (already moved)
            if (span < MinRangePct / 100 || span > MaxRangePct / 100) return;

            var stopLossPips = close * StopLossPct / 100 / Symbol.PipSize;
            if (BothSide) stopLossPips = (_highPrice - _lowPrice) / Symbol.PipSize;

            var risk = Account.Balance * RiskPct / 100;
            var buySetup = new OrderSetup(risk, TradeType.Buy, stopLossPips);
            this.PlaceOrder(buySetup, _highPrice);

            var sellSetup = new OrderSetup(risk, TradeType.Sell, stopLossPips);
            this.PlaceOrder(sellSetup, _lowPrice);
            DrawBox();
        }

        private void FindHighLow()
        {
            var time = Server.Time;
            var recentBars = _minBars.TakeLast(24 * 60);
            var bars = recentBars.Where(x => x.OpenTime >= time.AddDays(-1) &&
                x.OpenTime.TimeOfDay.IsInRange(_startTime, _endTime));

            _highPrice = bars.Max(b => b.High);
            _lowPrice = bars.Min(b => b.Low);
        }

        private void DrawBox()
        {
            var date = Server.Time.Date;
            var start = date.AddDays(StartTime <= EndTime ? 0 : -1) + StartTime.ToTimeSpan();
            var end = date + EndTime.ToTimeSpan();
            var close = date.AddDays(EndTime <= CloseTime ? 0 : 1) + CloseTime.ToTimeSpan();

            Chart.DrawRectangle($"Box {date}", start, _highPrice, end, _lowPrice, RangeColor);
            Chart.DrawTrendLine($"UpLevel {date}", end, _highPrice, close, _highPrice, RangeColor);
            Chart.DrawTrendLine($"DownLevel {date}", end, _lowPrice, close, _lowPrice, RangeColor);
        }

        private void ApplyPreset(Preset preset)
        {
            if (Presets.TryGetValue(preset, out var p))
            {
                (StartTime, EndTime, CloseTime, StopLossPct, MinRangePct, MaxRangePct, BothSide) = p;
                Print(p);
            }
        }

        public record Params(int StartTime, int EndTime, int CloseTime, double StopLossPct, double MinRangePct, double MaxRangePct, bool BothSide = false);
    }

    public static class IntExtensions
    {
        public static TimeSpan ToTimeSpan(this int time) =>
            new(time / 100, time % 100, 0);
    }

    public static class TimeSpanExtensions
    {
        // Handle ranges that cross midnight (e.g., 22:00 - 02:00)
        public static bool IsInRange(this TimeSpan time, TimeSpan start, TimeSpan end) =>
            start <= end
                ? time >= start && time < end
                : time >= start || time < end;

        // MT5 server time to EST conversion
        public static TimeSpan MtToEst(this TimeSpan time) =>
            time.Add(TimeSpan.FromHours(time.TotalHours < 7 ? 17 : -7));
    }

    public static class DateTimeExtensions
    {
        public static DateTime MtToEst(this DateTime time) =>
            time.AddHours(-7);
    }

    public static class RobotExtensions
    {
        private const bool AutoSpread = false;  // Adjust SL/TP for spread automatically

        public static void PlaceOrder(this Robot robot, OrderSetup setup, double entryPrice = default)
        {
            var spread = robot.Symbol.Spread / robot.Symbol.PipSize;
            // Reject orders with SL too tight (< 3x spread)
            if (setup.StopLossPips < spread * 3) return;

            var adj = AutoSpread ? spread : 0;
            var slPips = setup.StopLossPips + adj;
            var tpPips = setup.TakeProfitPips - adj;
            var vol = robot.Symbol.VolumeForFixedRisk(setup.RiskAmount, setup.StopLossPips);

            if (entryPrice == default)
            {
                robot.ExecuteMarketOrderAsync(setup.Direction, robot.SymbolName, vol,
                                              Constants.BotId, slPips, tpPips);
                return;
            }

            var isBuy = setup.Direction == TradeType.Buy;
            if (AutoSpread && isBuy) entryPrice += robot.Symbol.Spread;

            var isLimit = isBuy ? entryPrice < robot.Symbol.Bid : entryPrice > robot.Symbol.Ask;
            if (isLimit)
            {
                robot.PlaceLimitOrderAsync(setup.Direction, robot.SymbolName, vol, entryPrice,
                                           Constants.BotId, slPips, tpPips);
            }
            else
            {
                robot.PlaceStopOrderAsync(setup.Direction, robot.SymbolName, vol, entryPrice,
                                          Constants.BotId, slPips, tpPips);
            }
        }

        public static void CancelOrders(this Robot robot) =>
            robot.PendingOrders
                .Where(x => x.Label == Constants.BotId && x.SymbolName == robot.SymbolName)
                .ToList()
                .ForEach(x => robot.CancelPendingOrderAsync(x));

        public static void ClosePositions(this Robot robot) =>
            robot.Positions
                .Where(x => x.Label == Constants.BotId && x.SymbolName == robot.SymbolName)
                .ToList()
                .ForEach(x => robot.ClosePositionAsync(x));
    }

    public record OrderSetup(double RiskAmount, TradeType Direction, double StopLossPips, double? TakeProfitPips = null);
}
