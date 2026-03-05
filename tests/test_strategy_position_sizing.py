from src.config.strategy import StrategyConfig, load_strategy_config


def test_symbol_position_multiplier_fallback_rules() -> None:
    cfg = StrategyConfig(
        SYMBOL_POSITION_MULTIPLIERS={
            "KRW-BTC": 1.2,
            "KRW-ETH": 0,
            "KRW-XRP": "bad-value",
        }
    )

    assert cfg.get_symbol_position_multiplier("KRW-BTC") == 1.2
    assert cfg.get_symbol_position_multiplier("KRW-ETH") == 1.0
    assert cfg.get_symbol_position_multiplier("KRW-XRP") == 1.0
    assert cfg.get_symbol_position_multiplier("KRW-UNKNOWN") == 1.0


def test_load_strategy_config_reads_symbol_position_multipliers(tmp_path) -> None:
    config_file = tmp_path / "strategy.yaml"
    config_file.write_text(
        (
            "position_sizing:\n"
            "  symbol_position_multipliers:\n"
            "    KRW-BTC: 1.2\n"
            "    KRW-ETH: 1.1\n"
            "    KRW-XRP: 0.7\n"
        ),
        encoding="utf-8",
    )

    cfg = load_strategy_config(str(config_file))
    assert cfg.get_symbol_position_multiplier("KRW-BTC") == 1.2
    assert cfg.get_symbol_position_multiplier("KRW-ETH") == 1.1
    assert cfg.get_symbol_position_multiplier("KRW-XRP") == 0.7
    assert cfg.get_symbol_position_multiplier("KRW-SOL") == 1.0
