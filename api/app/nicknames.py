"""Friendly generated nicknames for anonymous players, e.g. "Sleepy Mango"."""
import random

ADJECTIVES = [
    "Brave", "Sleepy", "Curious", "Sneaky", "Happy", "Lazy", "Swift", "Gentle", "Clever",
    "Fluffy", "Quiet", "Lucky", "Bouncy", "Cheeky", "Dreamy", "Fuzzy", "Jolly", "Nimble",
    "Patient", "Sunny", "Wandering", "Whiskered", "Zippy", "Cosy", "Daring", "Mellow",
]
NOUNS = [
    "Mango", "Noodle", "Dumpling", "Lychee", "Coconut", "Durian", "Papaya", "Lotus",
    "Pepper", "Tofu", "Biscuit", "Jackfruit", "Tamarind", "Guava", "Rambutan", "Sesame",
    "Pomelo", "Ginger", "Peanut", "Longan", "Taro", "Mochi", "Bamboo", "Lemongrass",
]


def random_nickname() -> str:
    return f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}"
