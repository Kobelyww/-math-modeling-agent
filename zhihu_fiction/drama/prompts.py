"""Prompt templates for novel-to-short-drama adaptation."""
from __future__ import annotations


BLUEPRINT_PROMPT = """你是短剧改编策划。请把下面的知乎/网文小说改编成适合视频生成模型生产的竖屏短剧蓝图。

硬性规格：
- 最多 10 集。
- 每集 60-90 秒。
- 每集后半段必须有反转或悬念。
- 保留小说最强的情绪驱动和爽点。
- 删除不适合短视频呈现的冗长心理描写。
- 不要调用任何视频生成模型。

小说标题：{source_title}
题材：{genre}
发布方案参考：{synthesis}

小说正文：
{story}

只输出 JSON，字段如下：
{{
  "title": "短剧标题",
  "source_title": "{source_title}",
  "genre": "{genre}",
  "logline": "一句话卖点",
  "audience": "目标观众",
  "episode_count": 1,
  "characters": [
    {{
      "id": "heroine",
      "name": "角色名",
      "role": "角色功能",
      "age_range": "年龄段",
      "appearance": "稳定外貌",
      "costume": "稳定服装",
      "personality": "性格",
      "motivation": "核心动机",
      "consistency_prompt": "可复用的角色视觉一致性提示词"
    }}
  ],
  "locations": [
    {{
      "id": "living_room",
      "name": "场景名",
      "visual_style": "视觉风格",
      "time_period": "时代背景",
      "lighting": "灯光",
      "consistency_prompt": "可复用的场景一致性提示词"
    }}
  ],
  "episode_outline": [
    {{
      "index": 1,
      "title": "集标题",
      "hook": "开场钩子",
      "synopsis": "本集剧情",
      "cliffhanger": "结尾悬念"
    }}
  ],
  "adaptation_notes": ["改编策略"],
  "risk_notes": ["内容风险和规避方式"]
}}"""


SHOT_PACKAGE_PROMPT = """你是短剧分镜导演和视频模型 Prompt 工程师。请基于短剧蓝图，生成完整的镜头级短剧 Prompt 包。

硬性规格：
- episode_count 必须与蓝图一致，且不超过 10。
- 每集必须有 6-12 个镜头。
- 每个镜头 duration_seconds 必须在 5-8 秒之间。
- 每个镜头必须引用已存在的 character id 和 location id。
- 每个镜头必须有中文 action、dialogue、emotion。
- 每个镜头必须有 camera、visual_prompt、negative_prompt、consistency_refs。
- visual_prompt 可以使用英文或中英混合，必须利于视频模型理解。
- 不要输出 Markdown，不要解释，只输出 JSON。

原小说标题：{source_title}
题材：{genre}

短剧蓝图 JSON：
{blueprint_json}

小说正文参考：
{story}

输出 JSON 字段必须匹配：
{{
  "title": "短剧标题",
  "source_title": "{source_title}",
  "genre": "{genre}",
  "logline": "一句话卖点",
  "audience": "目标观众",
  "episode_count": 1,
  "characters": [],
  "locations": [],
  "episodes": [
    {{
      "index": 1,
      "title": "集标题",
      "hook": "开场钩子",
      "synopsis": "本集剧情",
      "cliffhanger": "结尾悬念",
      "shots": [
        {{
          "id": "ep01_sc01_sh01",
          "episode_index": 1,
          "scene_index": 1,
          "shot_index": 1,
          "duration_seconds": 6,
          "location_id": "living_room",
          "character_ids": ["heroine"],
          "action": "画面动作",
          "dialogue": "对白，没有对白时写空字符串",
          "emotion": "情绪",
          "camera": "camera movement and framing",
          "visual_prompt": "video generation prompt",
          "negative_prompt": "low quality, blurry, distorted face, inconsistent costume",
          "consistency_refs": ["character.heroine", "location.living_room"]
        }}
      ]
    }}
  ],
  "adaptation_notes": [],
  "risk_notes": []
}}"""


def build_blueprint_prompt(source_title: str, genre: str, story: str, synthesis: str = "") -> str:
    return BLUEPRINT_PROMPT.format(
        source_title=source_title,
        genre=genre or "未指定",
        story=story,
        synthesis=synthesis or "无",
    )


def build_shot_package_prompt(
    source_title: str,
    genre: str,
    story: str,
    blueprint_json: str,
) -> str:
    return SHOT_PACKAGE_PROMPT.format(
        source_title=source_title,
        genre=genre or "未指定",
        story=story,
        blueprint_json=blueprint_json,
    )
