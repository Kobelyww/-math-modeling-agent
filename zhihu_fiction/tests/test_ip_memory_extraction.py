from zhihu_fiction.ip_memory.consistency import review_consistency
from zhihu_fiction.ip_memory.extraction import extract_ip_memory_from_story
from zhihu_fiction.ip_memory.models import CharacterCard, IPMemory, StoryBible, WorldFact


def test_extract_ip_memory_from_story_creates_core_entities():
    story = """
    # 雨夜归来

    > 题材：复仇爽文

    林晚在山西运城的雨夜醒来。三年前，她被继母周岚赶出家门。
    这一次，林晚带着父亲死亡的录音证据归来。她发誓不能再让周岚篡改遗嘱。
    """

    memory = extract_ip_memory_from_story(
        project_id="story-rain",
        title="雨夜归来",
        genre="复仇爽文",
        story_text=story,
        story_ref="output/雨夜归来/小说正文.md",
    )

    assert memory.story_bible.title == "雨夜归来"
    assert memory.story_bible.genre == "复仇爽文"
    assert memory.story_bible.emotional_promise
    assert any(card.name == "林晚" for card in memory.characters)
    assert any(card.name == "周岚" for card in memory.characters)
    assert not any(card.name == "周岚赶" for card in memory.characters)
    assert any("运城" in fact.text for fact in memory.world_facts)
    assert any("遗嘱" in item.text or "录音" in item.text for item in memory.narrative_memory)
    assert memory.style_guide.tone
    assert memory.style_guide.pacing


def test_empty_extraction_keeps_prior_memory():
    prior = IPMemory(
        project_id="story-rain",
        story_bible=StoryBible(title="旧标题"),
        characters=[CharacterCard(id="char_old", name="旧角色")],
    )

    memory = extract_ip_memory_from_story(
        project_id="story-rain",
        title="",
        genre="",
        story_text="",
        prior=prior,
    )

    assert memory.story_bible.title == "旧标题"
    assert memory.characters[0].name == "旧角色"


def test_extraction_merges_prior_narrative_entries():
    prior = extract_ip_memory_from_story(
        project_id="story-rain",
        title="雨夜归来",
        genre="复仇爽文",
        story_text="林晚带着父亲死亡的录音证据归来。",
    )

    memory = extract_ip_memory_from_story(
        project_id="story-rain",
        title="雨夜归来",
        genre="复仇爽文",
        story_text="林晚在山西运城醒来。",
        prior=prior,
    )

    assert any("录音证据" in item.text for item in memory.narrative_memory)


def test_extraction_dedupes_prior_characters_world_facts_and_narrative():
    story = """
    林晚在山西运城的雨夜醒来。
    林晚带着父亲死亡的录音证据归来。
    """
    prior = extract_ip_memory_from_story(
        project_id="story-rain",
        title="雨夜归来",
        genre="复仇爽文",
        story_text=story,
    )

    memory = extract_ip_memory_from_story(
        project_id="story-rain",
        title="雨夜归来",
        genre="复仇爽文",
        story_text=story,
        prior=prior,
    )

    assert [card.name for card in memory.characters].count("林晚") == 1
    assert sum(1 for fact in memory.world_facts if "运城" in fact.text) == 1
    assert sum(1 for item in memory.narrative_memory if "录音证据" in item.text) == 1


def test_consistency_review_flags_contradicting_character_fact():
    memory = IPMemory(
        project_id="p",
        story_bible=StoryBible(title="A"),
        characters=[
            CharacterCard(id="char_linwan", name="林晚", visual_identity="黑色长发")
        ],
        world_facts=[
            WorldFact(id="fact_city", text="故事发生在现代运城", category="setting")
        ],
    )

    review = review_consistency(
        stage="storyboard",
        output="林晚变成短发金发女孩，故事发生在未来上海。",
        memory=memory,
    )

    assert review["status"] == "warning"
    assert any("林晚" in warning for warning in review["warnings"])
    assert any("现代运城" in warning for warning in review["warnings"])


def test_consistency_review_flags_extracted_modern_yuncheng_fact():
    memory = extract_ip_memory_from_story(
        project_id="story-rain",
        title="雨夜归来",
        genre="复仇爽文",
        story_text="林晚在山西运城的雨夜醒来。",
    )

    review = review_consistency(
        stage="storyboard",
        output="故事改成未来上海。",
        memory=memory,
    )

    assert review["status"] == "warning"
    assert any("运城" in warning for warning in review["warnings"])
