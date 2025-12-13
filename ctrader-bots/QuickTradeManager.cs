using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;

namespace cAlgo.Robots
{
    // Interface for accessing robot parameters from nested classes
    public interface IUserSetup
    {
        public double CashRisk { get; }
        public double CashRisk2 { get; }
        public bool IsMarketOrder { get; }
        public TradeType TradeDirection { get; }
        public double StopLossPips { get; }
        public double RewardRatio { get; }
        public string ExpiryTime { get; }
        public bool UseTrailingStop { get; }
        public double MaxRiskPct { get; }

        public HorizontalAlignment PanelHorizontalAlignment { get; }
        public VerticalAlignment PanelVerticalAlignment { get; }
    }

    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class QuickTradeManager : Robot, IUserSetup
    {
        private const string CriticalGroup = "Critical";
        private const string DefaultSettingsGroup = "Default settings";
        private const string PanelAlignmentGroup = "Panel alignment";
        private const string SecurityGroup = "Security";

        [Parameter("Cash Risk", Group = CriticalGroup, DefaultValue = 0, MinValue = 0, Step = 10)]
        public double CashRisk { get; set; }

        [Parameter("Cash Risk 2", Group = DefaultSettingsGroup, DefaultValue = 0, MinValue = 0, Step = 10)]
        public double CashRisk2 { get; set; }

        [Parameter("Market Order", Group = DefaultSettingsGroup, DefaultValue = true)]
        public bool IsMarketOrder { get; set; }

        [Parameter("Trade Direction", Group = DefaultSettingsGroup, DefaultValue = TradeType.Buy)]
        public TradeType TradeDirection { get; set; }

        [Parameter("Stop Loss Pips", Group = DefaultSettingsGroup, DefaultValue = 0, MinValue = 0, Step = 1)]
        public double StopLossPips { get; set; }

        [Parameter("Reward Ratio", Group = DefaultSettingsGroup, DefaultValue = 2, MinValue = 0, Step = .5)]
        public double RewardRatio { get; set; }

        [Parameter("Expiry Time (UTC)", Group = DefaultSettingsGroup, DefaultValue = "09:00, 15:00")]
        public string ExpiryTime { get; set; }

        [Parameter("Use Trailing Stop", Group = DefaultSettingsGroup, DefaultValue = false)]
        public bool UseTrailingStop { get; set; }

        [Parameter("Horizontal Position", Group = PanelAlignmentGroup, DefaultValue = HorizontalAlignment.Left)]
        public HorizontalAlignment PanelHorizontalAlignment { get; set; }

        [Parameter("Vertical Position", Group = PanelAlignmentGroup, DefaultValue = VerticalAlignment.Top)]
        public VerticalAlignment PanelVerticalAlignment { get; set; }

        [Parameter("Max Risk Percentage", Group = SecurityGroup, DefaultValue = 1.5, MaxValue = 100, MinValue = 0, Step = .5)]
        public double MaxRiskPct { get; set; }

        private TradingPanel tradingPanel;

        protected override void OnStart()
        {
            tradingPanel = new TradingPanel(this, this);
            Chart.AddControl(tradingPanel.GetPanel());
        }

        protected override void OnStop()
        {
            tradingPanel.OnStop();
        }
    }

    // UI panel with interactive controls and chart line management
    public class TradingPanel
    {
        private const string CashRiskKey = "CashRiskKey";
        private const string EntryPriceKey = "EntryPriceKey";
        private const string RewardRatioKey = "RewardRatioKey";
        private const string StopLossKey = "StopLossKey";
        // Input fields to disable in market order mode
        private static readonly IReadOnlyList<string> OrderModeKeys = new List<string>
        {
            EntryPriceKey, StopLossKey, RewardRatioKey
        };
        private readonly IDictionary<string, TextBox> inputMap = new Dictionary<string, TextBox>();
        private readonly Style buyButtonStyle, sellButtonStyle, inputStyle, invalidInputStyle;
        private readonly ControlBase panel;
        private readonly Robot robot;
        private readonly IUserSetup userSetup;
        private readonly PriceCalculator priceCalculator;
        private readonly ChartLine chartLine;
        private readonly TradeExecution tradeExecution;
        private readonly ExpiryManager expiryManager;
        private readonly ClickManager clickManager;
        private bool isMarketOrder;
        private Button directionButton;
        private CheckBox trailingCheck;
        private TradeType tradeDirection;

        public TradingPanel(Robot robot, IUserSetup userSetup)
        {
            this.robot = robot;
            this.userSetup = userSetup;
            chartLine = new ChartLine(robot);
            tradeExecution = new TradeExecution(robot);
            buyButtonStyle = Styles.CreateBuyButtonStyle();
            sellButtonStyle = Styles.CreateSellButtonStyle();
            inputStyle = Styles.CreateInputStyle();
            invalidInputStyle = Styles.CreateInvalidInputStyle();
            isMarketOrder = userSetup.IsMarketOrder;
            tradeDirection = userSetup.TradeDirection;
            priceCalculator = new(robot);
            chartLine = new(robot);
            tradeExecution = new(robot);
            expiryManager = new ExpiryManager(userSetup.ExpiryTime);
            clickManager = new ClickManager();
            panel = CreateTradingPanel();
            chartLine.LineChanged += OnLineChanged;
            UpdateLines();
        }

        public ControlBase GetPanel()
        {
            return panel;
        }

        public void OnStop()
        {
            chartLine.RemoveLines();
        }

        private ControlBase CreateTradingPanel()
        {
            var panel = new StackPanel { Margin = 10 };
            var grid = new Grid(3, 3);
            grid.Columns[1].SetWidthInPixels(5);

            var orderTypeButton = CreateOrderTypeButton();
            grid.AddChild(orderTypeButton, 0, 0);

            directionButton = CreateDirectionButton();
            grid.AddChild(directionButton, 0, 2);

            var inputGrid = CreateInputGrid();
            grid.AddChild(inputGrid, 1, 0, 1, 3);

            var previewButton = CreateButton("Preview", DefaultStyles.ButtonStyle, OnPreviewButtonClick);
            grid.AddChild(previewButton, 2, 0);

            var orderButton = CreateButton("Place Order", DefaultStyles.ButtonStyle, OnOrderButtonClick);
            grid.AddChild(orderButton, 2, 2);

            panel.AddChild(grid);
            var border = new Border
            {
                VerticalAlignment = userSetup.PanelVerticalAlignment,
                HorizontalAlignment = userSetup.PanelHorizontalAlignment,
                Style = Styles.CreatePanelBackgroundStyle(),
                Margin = "20 40 20 20",
                Width = 225,
                Child = panel
            };
            return border;
        }

        private ControlBase CreateInputGrid()
        {
            var border = new Border
            {
                Style = Styles.CreateBorderStyle(),
                Margin = "0 5 0 5",
                Padding = "0 5 0 5",
                BorderThickness = "0 1 0 1",
            };
            var grid = new Grid(6, 3);
            grid.Columns[1].SetWidthInPixels(5);

            var maxCashRisk = userSetup.MaxRiskPct / 100 * robot.Account.Balance;
            var cashRiskInput = CreateInputBox(CashRiskKey, userSetup.CashRisk, maxCashRisk);
            grid.AddChild(CreateTextBlock("Cash Risk"), 0, 0);
            grid.AddChild(cashRiskInput, 0, 2);

            var entryPriceInput = CreateInputBox(EntryPriceKey, robot.Symbol.Bid);
            grid.AddChild(CreateTextBlock("Entry Price"), 1, 0);
            grid.AddChild(entryPriceInput, 1, 2);

            var stopLossInput = CreateInputBox(StopLossKey, DefaultStopLoss());
            grid.AddChild(CreateTextBlock("Stop Loss"), 2, 0);
            grid.AddChild(stopLossInput, 2, 2);

            var ratioInput = CreateInputBox(RewardRatioKey, userSetup.RewardRatio);
            grid.AddChild(CreateTextBlock("Reward Ratio"), 3, 0);
            grid.AddChild(ratioInput, 3, 2);

            var setCashInput = CreateDefaultInput(CashRiskKey, userSetup.CashRisk, userSetup.CashRisk2);
            grid.AddChild(CreateTextBlock("Set Cash Risk"), 4, 0);
            grid.AddChild(setCashInput, 4, 2);

            trailingCheck = new CheckBox { Text = "Use Trailing Stop", IsChecked = userSetup.UseTrailingStop, Margin = 5 };
            grid.AddChild(trailingCheck, 5, 0, 1, 3);

            SetOrderTypeLine();
            border.Child = grid;

            return border;
        }

        private ControlBase CreateDefaultInput(string inputKey, double value, double value2)
        {
            var grid = new Grid(1, 2);
            var button = new Button { Text = value.ToString(), Margin = 5 };
            var button2 = new Button { Text = value2.ToString(), Margin = 5 };
            button.Click += e => SetValueToInput(inputKey, value);
            button2.Click += e => SetValueToInput(inputKey, value2);
            grid.AddChild(button, 0, 0);
            grid.AddChild(button2, 0, 1);
            return grid;
        }

        private Button CreateOrderTypeButton()
        {
            var button = CreateButton(isMarketOrder ? "Market" : "Pending", DefaultStyles.ButtonStyle, OnOrderTypeButtonClick);
            return button;
        }

        private Button CreateDirectionButton()
        {
            var isBuy = tradeDirection == TradeType.Buy;
            var button = CreateButton(isBuy ? "Buy" : "Sell", isBuy ? buyButtonStyle : sellButtonStyle, OnDirectionButtonClick);
            return button;
        }

        private TextBlock CreateTextBlock(string text, bool isCenter = false)
        {
            var textBlock = new TextBlock
            {
                Text = text,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = 5,
            };
            if (isCenter) textBlock.HorizontalAlignment = HorizontalAlignment.Center;
            return textBlock;
        }

        private TextBox CreateInputBox(string inputKey, double defaultValue, double maxValue = double.MaxValue)
        {
            var isValid = IsVaildInput(defaultValue.ToString(), maxValue);
            var input = new TextBox
            {
                Text = defaultValue.ToString(),
                Style = isValid ? inputStyle : invalidInputStyle,
                Margin = 5,
            };

            input.TextChanged += e => { OnTextChanged(e, maxValue); };
            inputMap.Add(inputKey, input);

            return input;
        }

        private Button CreateButton(string text, Style style, Action<ButtonClickEventArgs> action)
        {
            var button = new Button
            {
                Text = text,
                Style = style,
                Height = 25,
                Margin = 5,
            };
            button.Click += e => action(e);
            return button;
        }

        private void OnOrderTypeButtonClick(ButtonClickEventArgs e)
        {
            isMarketOrder = !isMarketOrder;
            e.Button.Text = isMarketOrder ? "Market" : "Pending";
            SetOrderTypeLine();
        }

        private void OnDirectionButtonClick(ButtonClickEventArgs e)
        {
            ChangeDirection();
            if (isMarketOrder)
            {
                var orderSetup = priceCalculator.PriceToOrder(chartLine.GetPrice());
                var direction = orderSetup.Direction == TradeType.Sell ? TradeType.Buy : TradeType.Sell;
                orderSetup = orderSetup with { Direction = direction };
                chartLine.UpdateLines(priceCalculator.OrderToPrice(orderSetup));
            }
            else
            {
                UpdateLines();
            }
        }

        private void OnTextChanged(TextChangedEventArgs e, double maxValue)
        {
            bool isValid = IsVaildInput(e.TextBox.Text, maxValue);
            e.TextBox.Style = isValid ? inputStyle : invalidInputStyle;
            UpdateLines();
        }

        private void OnPreviewButtonClick(ButtonClickEventArgs e)
        {
            var prices = isMarketOrder ? chartLine.GetPrice() : priceCalculator.OrderToPrice(GetUserInput());
            chartLine.ToggleLines(prices);
        }

        private void OnOrderButtonClick(ButtonClickEventArgs e)
        {
            if (clickManager.IsDoubleClick())
            {
                chartLine.HideLines();
                if (isMarketOrder)
                {
                    tradeExecution.MarketOrder(GetValueFromInput(CashRiskKey), chartLine.GetPrice(), trailingCheck.IsChecked == true);
                }
                else
                {
                    tradeExecution.PendingOrder(GetUserInput());
                }
            }
        }

        private void OnLineChanged(PriceRecord priceRecord)
        {
            var orderSetup = priceCalculator.PriceToOrder(priceRecord);
            if (isMarketOrder)
            {
                // Auto-switch direction when SL crosses current price
                if (tradeDirection != orderSetup.Direction)
                {
                    ChangeDirection();
                    chartLine.UpdateLines(priceCalculator.OrderToPrice(orderSetup));
                }
                return;
            }

            if (orderSetup.EntryPrice != GetValueFromInput(EntryPriceKey))
            {
                SetValueToInput(EntryPriceKey, orderSetup.EntryPrice);
            }
            else if (orderSetup.StopLoss != GetValueFromInput(StopLossKey))
            {
                if (tradeDirection != orderSetup.Direction) ChangeDirection();
                SetValueToInput(StopLossKey, orderSetup.StopLoss);
            }
            else if (orderSetup.RewardRatio != GetValueFromInput(RewardRatioKey))
            {
                SetValueToInput(RewardRatioKey, orderSetup.RewardRatio);
            }
            UpdateLines();
        }

        private OrderSetup GetUserInput()
        {
            if (!IsAllInputVaild()) return null;
            return new OrderSetup(
                GetValueFromInput(CashRiskKey),
                tradeDirection,
                GetValueFromInput(EntryPriceKey),
                GetValueFromInput(StopLossKey),
                GetValueFromInput(RewardRatioKey),
                expiryManager?.GetExpiry(),
                trailingCheck.IsChecked == true
            );
        }

        private bool IsVaildInput(string text, double maxValue)
        {
            return double.TryParse(text, out var result) && result >= 0 && result <= maxValue;
        }

        private bool IsAllInputVaild()
        {
            foreach (var item in inputMap)
            {
                if (item.Value.Style == invalidInputStyle) return false;
            }
            return true;
        }

        private void SetOrderTypeLine()
        {
            if (isMarketOrder)
            {
                EnableInputs(false);
                chartLine.HideEntryLine(0);
            }
            else
            {
                EnableInputs();
                chartLine.HideEntryLine(GetValueFromInput(EntryPriceKey));
                UpdateLines();
            }
        }

        private void EnableInputs(bool isEnabled = true)
        {
            foreach (var key in OrderModeKeys)
            {
                inputMap[key].IsEnabled = isEnabled;
            }
        }

        private void ChangeDirection()
        {
            var isBuy = tradeDirection == TradeType.Sell;
            tradeDirection = isBuy ? TradeType.Buy : TradeType.Sell;
            directionButton.Text = isBuy ? "Buy" : "Sell";
            directionButton.Style = isBuy ? buyButtonStyle : sellButtonStyle;
        }

        private double GetValueFromInput(string inputKey)
        {
            return double.Parse(inputMap[inputKey].Text);
        }

        private void SetValueToInput(string inputKey, double value)
        {
            inputMap[inputKey].Text = value.ToString();
        }

        private void UpdateLines()
        {
            chartLine.UpdateLines(priceCalculator.OrderToPrice(GetUserInput()));
        }

        private double DefaultStopLoss()
        {
            if (userSetup.StopLossPips > 0) return userSetup.StopLossPips;
            return Math.Round((robot.Chart.TopY - robot.Chart.BottomY) / robot.Symbol.PipSize / 10, 1);
        }
    }

    // Manages interactive horizontal lines on chart (entry, SL, TP)
    public class ChartLine
    {
        public event Action<PriceRecord> LineChanged;
        private const int LineThickness = 2;
        private readonly Robot robot;
        private ChartHorizontalLine entryLine, stopLossLine, takeProfitLine;
        private bool hideEntry = true;  // Hide entry line for market orders
        private PriceRecord lastPrice;

        public ChartLine(Robot robot)
        {
            this.robot = robot;
            CreateLines();
            robot.Chart.ObjectsUpdated += OnObjectUpdated;
            robot.Chart.ObjectsRemoved += OnObjectRemoved;
        }

        public void UpdateLines(PriceRecord priceRecord)
        {
            if (priceRecord == null)
            {
                HideLines();
                return;
            }

            if (!hideEntry) SetLine(entryLine, priceRecord.EntryPrice);
            SetLine(stopLossLine, priceRecord.StopLossPrice);
            SetLine(takeProfitLine, priceRecord.TakeProfitPrice);
            SaveLinePrice();
        }

        public void ToggleLines(PriceRecord priceRecord)
        {
            if (stopLossLine.IsHidden == false || priceRecord == null)
            {
                HideLines();
            }
            else
            {
                UpdateLines(priceRecord);
            }
        }

        public void HideLines()
        {
            entryLine.IsHidden = true;
            stopLossLine.IsHidden = true;
            takeProfitLine.IsHidden = true;
        }

        public void RemoveLines()
        {
            robot.Chart.ObjectsUpdated -= OnObjectUpdated;
            robot.Chart.ObjectsRemoved -= OnObjectRemoved;
            robot.Chart.RemoveObject(entryLine.Name);
            robot.Chart.RemoveObject(stopLossLine.Name);
            robot.Chart.RemoveObject(takeProfitLine.Name);
        }

        public PriceRecord GetPrice()
        {
            var entryPrice = hideEntry ? robot.Symbol.Bid : entryLine.Y;
            return new PriceRecord(entryPrice, stopLossLine.Y, takeProfitLine.Y);
        }

        public void HideEntryLine(double price)
        {
            hideEntry = price == 0;
            if (hideEntry)
            {
                entryLine.IsHidden = true;
            }
            else
            {
                SetLine(entryLine, price);
                SaveLinePrice();
            }
        }

        private void OnObjectUpdated(ChartObjectsUpdatedEventArgs e)
        {
            if (IsLineChanged())
            {
                LineChanged?.Invoke(GetPrice());
            }
        }

        private void OnObjectRemoved(ChartObjectsRemovedEventArgs e)
        {
            if (!(entryLine.IsAlive && stopLossLine.IsAlive && takeProfitLine.IsAlive))
            {
                CreateLines();
            }
        }

        private void CreateLines()
        {
            entryLine = CreateLine("entryLine", Color.Blue);
            stopLossLine = CreateLine("stopLossLine", Color.Red);
            takeProfitLine = CreateLine("takeProfitLine", Color.Green);
            RestoreLine();
        }

        private void SetLine(ChartHorizontalLine line, double price)
        {
            line.Y = price;
            line.IsHidden = false;
        }

        private ChartHorizontalLine CreateLine(string name, Color color)
        {
            var line = robot.Chart.DrawHorizontalLine(name, 0, color, LineThickness, LineStyle.Dots);
            line.IsInteractive = true;
            line.IsHidden = true;
            return line;
        }

        private void SaveLinePrice()
        {
            lastPrice = GetPrice();
        }

        private bool IsLineChanged()
        {
            return !(lastPrice == GetPrice());
        }

        private void RestoreLine()
        {
            if (lastPrice != null)
            {
                entryLine.Y = lastPrice.EntryPrice;
                stopLossLine.Y = lastPrice.StopLossPrice;
                takeProfitLine.Y = lastPrice.TakeProfitPrice;
            }
        }
    }

    // Executes market and pending orders with volume calculation
    public class TradeExecution
    {
        private const string OrderIdentifier = "Quick Trade Manager";
        private readonly Robot robot;

        public TradeExecution(Robot robot)
        {
            this.robot = robot;
        }

        public void MarketOrder(double cashRisk, PriceRecord priceRecord, bool hasTrailingStop = false)
        {
            var isBuy = robot.Symbol.Bid > priceRecord.StopLossPrice;
            var direction = isBuy ? TradeType.Buy : TradeType.Sell;
            var entryPrice = isBuy ? robot.Symbol.Ask : robot.Symbol.Bid;
            var stopLoss = Math.Abs((entryPrice - priceRecord.StopLossPrice) / robot.Symbol.PipSize);
            var takeProfit = Math.Abs((entryPrice - priceRecord.TakeProfitPrice) / robot.Symbol.PipSize);
            var volume = CalculateVolumeInUnits(cashRisk, stopLoss);
            robot.ExecuteMarketOrderAsync(direction, robot.SymbolName, volume, OrderIdentifier, stopLoss, takeProfit, "", hasTrailingStop);
        }

        public void PendingOrder(OrderSetup orderSetup)
        {
            if (orderSetup == null) return;

            var isBuyOrder = orderSetup.Direction == TradeType.Buy;
            var volumeInUnits = CalculateVolumeInUnits(orderSetup.CashRisk, orderSetup.StopLoss);
            var takeProfit = orderSetup.StopLoss * orderSetup.RewardRatio;

            // Limit order if entry is better than current price, Stop order otherwise
            if ((isBuyOrder && orderSetup.EntryPrice < robot.Symbol.Ask) ||
                (!isBuyOrder && orderSetup.EntryPrice > robot.Symbol.Bid))
            {
                robot.PlaceLimitOrderAsync(orderSetup.Direction, robot.SymbolName, volumeInUnits, orderSetup.EntryPrice,
                    OrderIdentifier, orderSetup.StopLoss, takeProfit, orderSetup.Expiry, "", orderSetup.HasTrailingStop);
            }
            else
            {
                robot.PlaceStopOrderAsync(orderSetup.Direction, robot.SymbolName, volumeInUnits, orderSetup.EntryPrice,
                    OrderIdentifier, orderSetup.StopLoss, takeProfit, orderSetup.Expiry, "", orderSetup.HasTrailingStop);
            }
        }

        private double CalculateVolumeInUnits(double cashRisk, double stopLoss)
        {
            var volumeInUnitsStep = robot.Symbol.VolumeInUnitsStep;
            return Math.Round(cashRisk / (stopLoss * robot.Symbol.PipValue) / volumeInUnitsStep) * volumeInUnitsStep;
        }
    }

    public static class Styles
    {
        public static Style CreatePanelBackgroundStyle()
        {
            var style = new Style();
            style.Set(ControlProperty.CornerRadius, 3);
            SetThemeStyle(style, ControlProperty.BackgroundColor, "#292929", "#FFFFFF", 0.85m);
            SetThemeStyle(style, ControlProperty.BorderColor, "#3C3C3C", "#C3C3C3");
            style.Set(ControlProperty.BorderThickness, new Thickness(1));
            return style;
        }

        public static Style CreateBorderStyle()
        {
            var style = new Style();
            SetThemeStyle(style, ControlProperty.BorderColor, Color.White, Color.Black, 0.12m);
            return style;
        }

        public static Style CreateBuyButtonStyle()
        {
            return CreateButtonStyle("#009345", "#10A651");
        }

        public static Style CreateSellButtonStyle()
        {
            return CreateButtonStyle("#F05824", "#FF6C36");
        }

        public static Style CreateInputStyle()
        {
            var style = new Style(DefaultStyles.TextBoxStyle);
            SetThemeStyle(style, ControlProperty.BackgroundColor, "#1A1A1A", "#E7EBED");
            SetThemeHoverStyle(style, "#111111", "#D6DADC");
            return style;
        }

        public static Style CreateInvalidInputStyle()
        {
            var style = new Style(DefaultStyles.TextBoxStyle);
            SetThemeStyle(style, ControlProperty.BackgroundColor, "#A45D5D", "#FF8080");
            SetThemeHoverStyle(style, "#BA5353", "#FF6E6E");
            return style;
        }

        private static Style CreateButtonStyle(Color color, Color hoverColor)
        {
            var style = new Style(DefaultStyles.ButtonStyle);
            SetThemeStyle(style, ControlProperty.BackgroundColor, color, color);
            SetThemeStyle(style, ControlProperty.ForegroundColor, Color.White, Color.White);
            SetThemeHoverStyle(style, hoverColor, hoverColor);
            return style;
        }

        private static void SetThemeStyle(Style style, ControlProperty property, Color darkColor, Color lightColor, decimal opacity = 1.0m)
        {
            style.Set(property, GetColorWithOpacity(darkColor, opacity), ControlState.DarkTheme);
            style.Set(property, GetColorWithOpacity(lightColor, opacity), ControlState.LightTheme);
        }

        private static void SetThemeHoverStyle(Style style, Color darkColor, Color lightColor)
        {
            style.Set(ControlProperty.BackgroundColor, darkColor, ControlState.DarkTheme | ControlState.Hover);
            style.Set(ControlProperty.BackgroundColor, lightColor, ControlState.LightTheme | ControlState.Hover);
        }

        private static Color GetColorWithOpacity(Color baseColor, decimal opacity)
        {
            var alpha = (int)Math.Round(byte.MaxValue * opacity, MidpointRounding.AwayFromZero);
            return Color.FromArgb(alpha, baseColor);
        }
    }

    // Parses expiry times (e.g., "09:00, 15:00") to generate this week's datetime list
    public class ExpiryManager
    {
        private const char TimeDelimiter = ',';
        private readonly List<DateTime> expiryList;

        public ExpiryManager(string expiryString)
        {
            expiryList = ParseExpiry(expiryString);
        }

        public DateTime? GetExpiry()
        {
            return expiryList.FirstOrDefault(e => e > DateTime.UtcNow);
        }

        private List<DateTime> ParseExpiry(string expiryString)
        {
            var timeExpiry = expiryString.Split(TimeDelimiter)
                .Select(TimeOnly.Parse)
                .ToList();

            var currentDate = DateOnly.FromDateTime(DateTime.UtcNow);
            var currentWeekStart = TimeUtils.GetMondayOfWeek(currentDate);

            // Generate expiry times for Mon-Fri this week
            return Enumerable.Range(0, 5)
                .Select(i => currentWeekStart.AddDays(i))
                .SelectMany(date => timeExpiry.Select(time => new DateTime(date.Year, date.Month, date.Day, time.Hour, time.Minute, 0)))
                .ToList();
        }
    }

    public class PriceCalculator
    {
        private readonly Robot robot;

        public PriceCalculator(Robot robot)
        {
            this.robot = robot;
        }

        public PriceRecord OrderToPrice(OrderSetup orderSetup)
        {
            if (orderSetup == null) return null;
            var isBuy = orderSetup.Direction == TradeType.Buy;
            var entryPrice = orderSetup.EntryPrice;
            var stopLoss = orderSetup.StopLoss * robot.Symbol.PipSize;
            var stopLossPrice = entryPrice + (isBuy ? -1 : 1) * stopLoss;
            var takeProfitPrice = entryPrice + (isBuy ? 1 : -1) * stopLoss * orderSetup.RewardRatio;
            return new PriceRecord(entryPrice, stopLossPrice, takeProfitPrice);
        }

        public OrderSetup PriceToOrder(PriceRecord priceRecord)
        {
            var entryPrice = Math.Round(priceRecord.EntryPrice, robot.Symbol.Digits);
            var direction = entryPrice > priceRecord.StopLossPrice ? TradeType.Buy : TradeType.Sell;
            var stopLoss = Math.Abs(entryPrice - priceRecord.StopLossPrice);
            var stopLossPips = Math.Round(stopLoss / robot.Symbol.PipSize, 1);
            var rewardRatio = Math.Round(Math.Abs(entryPrice - priceRecord.TakeProfitPrice) / stopLoss, 2);
            return new OrderSetup(0, direction, entryPrice, stopLossPips, rewardRatio);
        }
    }

    // Prevents accidental order placement (requires double-click + cooldown)
    public class ClickManager
    {
        private const int DoubleClickInterval = 500;  // ms
        private const int OrderCooldownMillis = 1000;  // ms between orders
        private DateTime lastButtonClickTime, lastOrderTime;

        public bool IsDoubleClick()
        {
            var now = DateTime.UtcNow;
            var isDoubleClick = (now - lastButtonClickTime).TotalMilliseconds < DoubleClickInterval;
            lastButtonClickTime = now;

            var isCooldownPassed = (now - lastOrderTime).TotalMilliseconds > OrderCooldownMillis;
            var isPassed = isDoubleClick && isCooldownPassed;
            if (isPassed) lastOrderTime = now;

            return isPassed;
        }
    }

    public static class TimeUtils
    {
        public static DateOnly GetMondayOfWeek(DateOnly date)
        {
            return date.AddDays(-(int)date.DayOfWeek + (int)DayOfWeek.Monday);
        }
    }

    public record PriceRecord(double EntryPrice, double StopLossPrice, double TakeProfitPrice);
    public record OrderSetup(double CashRisk, TradeType Direction, double EntryPrice, double StopLoss, double RewardRatio, DateTime? Expiry = null, bool HasTrailingStop = false);
}
