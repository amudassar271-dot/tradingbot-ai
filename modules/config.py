from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


@dataclass(frozen=True)
class PortfolioConfig:
    capital_nok: float
    max_positions: int
    position_sizing: str
    max_position_pct: float
    cash_reserve_pct: float


@dataclass(frozen=True)
class RiskConfig:
    stop_loss_pct: float
    take_profit_pct: float
    minimum_buy_score: int


@dataclass(frozen=True)
class TransactionCostConfig:
    fixed_nok: float


@dataclass(frozen=True)
class TradingConfig:
    min_trade_size_nok: float
    max_new_positions_per_rebalance: int
    rebalance_frequency: str
    min_holding_days: int
    min_score_for_buy: int
    min_score_for_reentry: int


@dataclass(frozen=True)
class PrimaryStrategyConfig:
    name: str
    top_n: int
    rebalance_frequency: str
    stop_loss_pct: float
    momentum_threshold_pct: float
    capital_nok: float


@dataclass(frozen=True)
class BacktestConfig:
    history_period: str
    rebalance_frequency: str
    output_path: Path


@dataclass(frozen=True)
class NewsConfig:
    enabled: bool
    max_headlines_per_ticker: int
    sentiment_enabled: bool
    cache_path: Path
    output_path: Path


@dataclass(frozen=True)
class SignalConfig:
    sell_momentum_threshold: float


@dataclass(frozen=True)
class ReportConfig:
    schedule: str
    output_path: Path


@dataclass(frozen=True)
class MarketDataConfig:
    watchlist_path: Path
    history_months: int


@dataclass(frozen=True)
class AppConfig:
    portfolio: PortfolioConfig
    risk: RiskConfig
    transaction_costs: TransactionCostConfig
    primary_strategy: PrimaryStrategyConfig
    trading: TradingConfig
    backtest: BacktestConfig
    news: NewsConfig
    signals: SignalConfig
    report: ReportConfig
    market_data: MarketDataConfig


def load_config(path: Path, base_dir: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = load_yaml(path)

    portfolio = raw.get("portfolio", {})
    risk = raw.get("risk", {})
    transaction_costs = raw.get("transaction_cost", raw.get("transaction_costs", {}))
    primary_strategy = raw.get("primary_strategy", {})
    trading = raw.get("trading", {})
    backtest = raw.get("backtest", {})
    news = raw.get("news", {})
    signals = raw.get("signals", {})
    report = raw.get("report", {})
    market_data = raw.get("market_data", {})

    return AppConfig(
        portfolio=PortfolioConfig(
            capital_nok=float(portfolio["capital_nok"]),
            max_positions=int(portfolio["max_positions"]),
            position_sizing=str(portfolio["position_sizing"]),
            max_position_pct=float(portfolio["max_position_pct"]),
            cash_reserve_pct=float(portfolio["cash_reserve_pct"]),
        ),
        risk=RiskConfig(
            stop_loss_pct=float(risk["stop_loss_pct"]),
            take_profit_pct=float(risk["take_profit_pct"]),
            minimum_buy_score=int(risk.get("min_score_for_buy", risk["minimum_buy_score"])),
        ),
        transaction_costs=TransactionCostConfig(
            fixed_nok=float(transaction_costs["fixed_nok"]),
        ),
        primary_strategy=PrimaryStrategyConfig(
            name=str(primary_strategy.get("name", "momentum_portfolio")),
            top_n=int(primary_strategy.get("top_n", 2)),
            rebalance_frequency=str(primary_strategy.get("rebalance_frequency", "monthly")),
            stop_loss_pct=normalize_percentage(primary_strategy.get("stop_loss_pct", 15)),
            momentum_threshold_pct=normalize_percentage(primary_strategy.get("momentum_threshold_pct", 10)),
            capital_nok=float(primary_strategy.get("capital_nok", portfolio["capital_nok"])),
        ),
        trading=TradingConfig(
            min_trade_size_nok=float(trading.get("min_trade_size_nok", 0)),
            max_new_positions_per_rebalance=int(trading.get("max_new_positions_per_rebalance", portfolio["max_positions"])),
            rebalance_frequency=str(trading.get("rebalance_frequency", backtest.get("rebalance_frequency", "monthly"))),
            min_holding_days=int(trading.get("min_holding_days", 0)),
            min_score_for_buy=int(trading.get("min_score_for_buy", risk.get("min_score_for_buy", risk["minimum_buy_score"]))),
            min_score_for_reentry=int(trading.get("min_score_for_reentry", trading.get("min_score_for_buy", risk.get("min_score_for_buy", risk["minimum_buy_score"])))),
        ),
        backtest=BacktestConfig(
            history_period=str(backtest["history_period"]),
            rebalance_frequency=str(trading.get("rebalance_frequency", backtest["rebalance_frequency"])),
            output_path=resolve_project_path(base_dir, backtest["output_path"]),
        ),
        news=NewsConfig(
            enabled=bool(news.get("enabled", True)),
            max_headlines_per_ticker=int(news.get("max_headlines_per_ticker", 3)),
            sentiment_enabled=bool(news.get("sentiment_enabled", True)),
            cache_path=resolve_project_path(base_dir, news.get("cache_path", "data/news_cache.json")),
            output_path=resolve_project_path(base_dir, news.get("output_path", "reports/news_report.md")),
        ),
        signals=SignalConfig(
            sell_momentum_threshold=float(signals["sell_momentum_threshold"]),
        ),
        report=ReportConfig(
            schedule=str(report["schedule"]),
            output_path=resolve_project_path(base_dir, report["output_path"]),
        ),
        market_data=MarketDataConfig(
            watchlist_path=resolve_project_path(base_dir, market_data["watchlist_path"]),
            history_months=int(market_data["history_months"]),
        ),
    )


def resolve_project_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> dict:
    parsed = {}
    current_section = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            parsed[current_section] = {}
            continue

        if current_section is None or ":" not in line:
            raise ValueError("Config fallback parser only supports simple section/key YAML")

        key, value = line.strip().split(":", 1)
        parsed[current_section][key.strip()] = parse_scalar(value.strip())

    return parsed


def parse_scalar(value: str):
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"

    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("\"'")


def normalize_percentage(value) -> float:
    percentage = float(value)
    if percentage > 1:
        return percentage / 100
    return percentage
