import config as config_module


def _load_fresh_config(monkeypatch):
    monkeypatch.setattr(config_module, "_config_instance", None)
    return config_module.Config.load()


def test_default_embedding_configuration_keeps_existing_index(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("CHROMA_PATH", raising=False)
    monkeypatch.delenv("ENGLISH_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("ENGLISH_CHROMA_PATH", raising=False)

    config = _load_fresh_config(monkeypatch)

    assert config.embedding_model == "BAAI/bge-small-zh-v1.5"
    assert config.chroma_path == "../data/chroma_db"
    assert config.english_embedding_model == "BAAI/bge-base-en-v1.5"
    assert config.english_chroma_path == "../data/chroma_db_bge_base_en"


def test_english_embedding_configuration_can_be_overridden_independently(
    monkeypatch,
):
    monkeypatch.setenv("ENGLISH_EMBEDDING_MODEL", "custom/english-model")
    monkeypatch.setenv("ENGLISH_CHROMA_PATH", "../data/custom_english_index")

    config = _load_fresh_config(monkeypatch)

    assert config.embedding_model == "BAAI/bge-small-zh-v1.5"
    assert config.chroma_path == "../data/chroma_db"
    assert config.english_embedding_model == "custom/english-model"
    assert config.english_chroma_path == "../data/custom_english_index"
