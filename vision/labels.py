"""YOLO label taxonomy for live board tracking and snapshot inspection."""

FRUIT_VEGETABLE_CLASSES = {
    "apple", "banana", "orange", "carrot", "broccoli",
    "tomato", "lemon", "pear", "peach", "strawberry",
    "potato", "cucumber", "onion", "pepper", "eggplant",
    "grape", "mango", "watermelon", "melon", "cherry",
    "zucchini",
    "fresh", "spoiled", "rotten", "bad", "good",
}

BOARD_LABEL_KEYWORDS = (
    "dining table",
    "table",
    "cutting board",
    "cutting-board",
    "tray",
    "counter",
    "desk",
)

ROBOT_LABEL_KEYWORDS = (
    "robot",
    "delta robot",
    "delta_robot",
    "robotic arm",
    "robotic_arm",
    "manipulator",
    "industrial robot",
)

PRODUCE_ALIASES = {
    "bell pepper": "pepper",
    "capsicum": "pepper",
    "sweet pepper": "pepper",
    "chili": "pepper",
    "chilli": "pepper",
    "aubergine": "eggplant",
    "courgette": "zucchini",
    "scallion": "onion",
}


def classify_yolo_label(label: str):
    """
    Map a YOLO class name to a coarse detection_type and canonical label.

    detection_type:
      produce, human, base_board, delta_robot, object, skip
    """
    normalized = (label or "").strip().lower()
    canonical_kind = PRODUCE_ALIASES.get(normalized, normalized)

    produce_keywords = (
        "fruit",
        "vegetable",
        "veg",
        "apple",
        "potato",
        "carrot",
        "tomato",
        "fresh",
        "rotten",
        "spoiled",
        "good",
        "bad",
    )
    if canonical_kind in FRUIT_VEGETABLE_CLASSES or any(
        kw in normalized for kw in produce_keywords
    ):
        return "produce", canonical_kind

    if normalized == "person":
        return "human", "person"

    if any(kw in normalized for kw in BOARD_LABEL_KEYWORDS):
        return "base_board", canonical_kind

    if any(kw in normalized for kw in ROBOT_LABEL_KEYWORDS):
        return "delta_robot", canonical_kind

    return "skip", None
