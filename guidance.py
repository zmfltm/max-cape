"""Deterministic, account-aware guidance for the next maxing action."""

import re


TRAINING = re.compile(
    r"^Train (?P<skill>[A-Za-z]+?)(?: level)? from level \d+ to level "
    r"(?P<target>\d+)"
)
COMBAT_TRAINING = re.compile(r"^Train Combat level to (?P<target>\d+)")
BATCH_SIZE = 6


def _level(stats, skill):
    if skill == "Combat":
        return int(stats.get("combat") or 0)
    return int(((stats.get("skills") or {}).get(skill) or {}).get("level") or 0)


def training_gate(step, stats):
    """Return an unmet guide training step in a structured form, or None."""
    if step.get("kind") != "task":
        return None
    text = str(step.get("name") or "")
    match = TRAINING.match(text)
    if match:
        skill = match.group("skill")
        target = int(match.group("target"))
    else:
        match = COMBAT_TRAINING.match(text)
        if not match:
            return None
        skill = "Combat"
        target = int(match.group("target"))
    current = _level(stats, skill)
    if current >= target:
        return None
    return {"skill": skill, "current": current, "target": target, "text": text}


def _training_action(gate, stats):
    skill, current, target = gate["skill"], gate["current"], gate["target"]
    if skill == "Ranged" and _level(stats, "Slayer") < 74:
        return {
            "headline": f"Train Ranged to {target} through Slayer",
            "summary": (
                f"Your next quest gate needs {target} Ranged. Cannon suitable "
                "Slayer tasks so this training also advances Slayer and combat."
            ),
            "actions": [
                f"Get a Nieve or Steve task and cannon suitable assignments until {target} Ranged.",
                "Use Strength on non-cannon melee tasks.",
                "Stop at the quest requirement; do not turn this into a 99 grind.",
            ],
        }
    if skill == "Slayer":
        master = "Duradel" if _level(stats, "Combat") >= 100 else "Nieve or Steve"
        return {
            "headline": f"Train Slayer from {current} to {target}",
            "summary": (
                f"The optimal quest route has reached a real {target} Slayer gate. "
                "This is the point where a Slayer block saves time rather than delaying unlocks."
            ),
            "actions": [
                f"Use {master} until {target} Slayer.",
                "Cannon suitable tasks and burst multi-combat tasks when available.",
                "Return to the quest route as soon as the requirement is met.",
            ],
        }
    return {
        "headline": f"Train {skill} from {current} to {target}",
        "summary": (
            f"The next useful quest block is gated by {target} {skill}. Train only "
            "to the requirement, then return to questing."
        ),
        "actions": [f"Train {skill} to {target}.",
                    "Stop at the requirement and resume the optimal quest route."],
    }


def _tracked(step):
    return step.get("state") in (0, 1)


def recommend(stats, quests, diaries=None):
    """Choose the next action from live levels and the snapshotted guide route."""
    route = list((quests or {}).get("route") or [])
    if not stats or not route:
        return {
            "headline": "Sync your character first",
            "summary": "Live Hiscores and WikiSync data are needed before guidance is reliable.",
            "actions": ["Run the local server and sync the linked character."],
        }

    next_index = next((i for i, step in enumerate(route) if _tracked(step)), None)
    if next_index is None:
        return {
            "headline": "The optimal quest route is complete",
            "summary": "Move to the next progression phase shown on the overview.",
            "actions": ["Complete hard diaries, then continue the Slayer-first max route."],
        }

    # Untracked guide actions and training rows can sit immediately before the
    # next quest. They matter even though WikiSync cannot mark them complete.
    previous = max(
        (i for i, step in enumerate(route[:next_index]) if step.get("state") == 2),
        default=-1,
    )
    between = route[previous + 1:next_index]
    immediate_gate = next((training_gate(step, stats) for step in between
                           if training_gate(step, stats)), None)
    if immediate_gate:
        result = _training_action(immediate_gate, stats)
        result["next_quest"] = route[next_index].get("name")
        return result

    immediate_tasks = [
        str(step.get("name")) for step in between
        if (step.get("kind") == "task"
            and not str(step.get("name") or "").startswith("Train ")
            and not training_gate(step, stats))
    ]

    batch = []
    future_gate = next(
        (training_gate(step, stats) for step in route[next_index:]
         if training_gate(step, stats)),
        None,
    )
    after_task = None
    batch_full_at = None
    for index, step in enumerate(route[next_index:], next_index):
        if _tracked(step):
            if len(batch) < BATCH_SIZE:
                batch.append(str(step.get("name")))
                if len(batch) == BATCH_SIZE:
                    batch_full_at = index
            elif batch_full_at is not None:
                break
        elif (batch_full_at is not None and step.get("kind") == "task"
              and not str(step.get("name") or "").startswith("Train ")
              and after_task is None):
            after_task = str(step.get("name"))

    first = batch[0] if batch else str(route[next_index].get("name") or "next quest")
    actions = [f"If not already done, complete the guide action: {name}."
               for name in immediate_tasks[:2]]
    actions += [f"Complete {name}." for name in batch]
    if after_task:
        actions.append(f"Then do the guide action: {after_task}.")

    result = {
        "headline": f"Quest now: {first}",
        "summary": (
            "Quest rewards and unlocks are more valuable than an ungated skill grind here. "
            "Work through this manageable batch, then reassess."
        ),
        "actions": actions,
    }
    if future_gate:
        result["checkpoint"] = _training_action(future_gate, stats)["headline"]
    if _level(stats, "Slayer") < 74:
        result["reward_note"] = (
            "Put selectable quest and diary XP into Slayer; only train it manually "
            "when the route reaches a real Slayer gate."
        )
    return result
