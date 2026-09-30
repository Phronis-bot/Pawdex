"""Breeds: detected by a classifier trained on Commons photos (cats; see
tools/train_breeds.py) or CLIP zero-shot (dogs), only when the model is confident.

Most street animals are mixed, so "mixed breed" competes with every breed and wins
ties. A breed never changes rarity (that is by coat). It is shown on the animal's
card and share image, never on the map: purebred animals are the ones that get stolen.

Texts are for players: short, true, and hedged ("said to", "legend has it") where a
story is folklore rather than documented history.
"""
import enum
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from app.classifier import ZeroShot, get_classifier
from app.config import settings
from app.models import Species


@dataclass(frozen=True)
class Breed:
    label: str
    origin: str
    history: str
    # Relatives and look-alikes: who it's confused with and how they're related.
    relatives: str
    facts: tuple[str, ...]
    # CLIP prompt name when the label alone is ambiguous.
    prompt_name: str | None = None
    # Whether CLIP zero-shot may claim it (species without a trained head, i.e. dogs), and
    # whether it gets a zero-shot prompt. False for breeds zero-shot confused with street
    # animals, and for breeds only the trained head knows. With a head, the head decides.
    detectable: bool = True


# "Mixed" prompts per species: what an ordinary street animal looks like.
MIXED_PROMPTS: dict[Species, list[str]] = {
    Species.cat: [
        "a photo of a mixed-breed street cat",
        "a photo of a stray domestic shorthair cat",
        "a photo of an ordinary alley cat",
    ],
    Species.dog: [
        "a photo of a mixed-breed street dog",
        "a photo of a stray mongrel dog",
        "a photo of an ordinary village dog",
    ],
}

BREEDS: dict[Species, dict[str, Breed]] = {
    Species.cat: {
        "siamese": Breed(
            "Siamese", "Thailand",
            "Pointed cats appear in the Tamra Maew, cat poems from the old kingdom of Siam (today's "
            "Thailand), written some time between the 14th and 18th centuries. Siamese reached Britain "
            "and the USA in the 1870s–1880s; many early ones had crossed eyes and kinked tails, traits "
            "breeders later bred out.",
            "Its colour-point gene lives on in the Birman, Ragdoll, Himalayan and Russia's Neva "
            "Masquerade. The Oriental Shorthair is essentially a Siamese in solid colours.",
            (
                "Siamese are famously talkative, with a loud, low voice.",
                "Their points darken with age and in cold weather: the pigment enzyme only works in cooler skin.",
            ),
        ),
        "oriental_shorthair": Breed(
            "Oriental Shorthair", "United Kingdom · Thailand (roots)",
            "A Siamese in any colour: in the 1950s–60s British breeders crossed Siamese with other "
            "shorthairs to keep the Siamese body and personality without the colour points. Today it "
            "comes in hundreds of colours and patterns.",
            "The Siamese is its closest relative — same build, but only in pointed colours. The Havana "
            "Brown shares its chocolate coat; the Oriental Longhair is its long-haired version.",
            (
                "Huge ears and a long wedge-shaped head make it one of the most striking cats.",
                "Like the Siamese, it's famously talkative and sociable.",
            ),
        ),
        "havana_brown": Breed(
            "Havana Brown", "United Kingdom · USA",
            "Solid brown cats already appear in the old Thai Tamra Maew poems. The modern breed was "
            "developed in Britain in the 1950s from Siamese and black shorthair crosses; the name "
            "probably comes from the colour of Havana cigars.",
            "Close to a chocolate Oriental Shorthair, but with a rounder muzzle and a more moderate build.",
            (
                "Even its whiskers are brown.",
                "It's one of the rarest pedigree breeds, with few kittens registered each year.",
            ),
            # A solid brown cat with no other tell: a black street cat in dim light
            # (Gladstone) "looked like" a Havana.
            detectable=False,
        ),
        "khao_manee": Breed(
            "Khao Manee", "Thailand",
            "An all-white cat kept in Thailand for centuries and described in the Tamra Maew. Its name "
            "means 'white gem'. It was almost unknown outside Thailand until the late 20th century.",
            "Easily confused with any white street cat — only a pedigree tells them apart.",
            (
                "Odd-coloured eyes, one blue and one gold, are especially prized.",
                "Like other white cats with blue eyes, some are born deaf.",
            ),
            detectable=False,
        ),
        "korat": Breed(
            "Korat", "Thailand",
            "From the Korat plateau of north-eastern Thailand, and also described in the Tamra Maew. "
            "Traditionally a symbol of good luck, given as a gift to newlyweds.",
            "Looks like a Russian Blue or Chartreux, but has a heart-shaped face and bright green eyes.",
            (
                "Its silver-tipped blue coat is compared to rain clouds, a good omen for rice farmers.",
                "Korat kittens' eyes start amber and turn green over two to four years.",
            ),
            detectable=False,
        ),
        "birman": Breed(
            "Birman", "Myanmar (legend) · France",
            "Legend says the 'Sacred Cat of Burma' guarded a temple, and its paws turned white where "
            "they touched a dying priest. The breed itself was developed in France in the 1920s.",
            "Shares its colour points with the Siamese and looks like a smaller Ragdoll — but only the "
            "Birman has pure white 'gloves' on all four paws.",
            (
                "Birman kittens are born completely white.",
                "Like all French pedigree animals, French-born Birmans get names starting with that "
                "year's letter of the alphabet.",
            ),
        ),
        "burmese": Breed(
            "Burmese", "Myanmar · USA",
            "Almost every Burmese traces back to Wong Mau, a brown cat brought from Burma to San "
            "Francisco in 1930. She was probably a Siamese–Burmese hybrid.",
            "A cousin of the Siamese; crossing the two gives the Tonkinese.",
            (
                "Burmese feel heavy for their size — 'bricks wrapped in silk', as breeders say.",
                "American and European Burmese are bred to different looks: rounder heads in the USA.",
            ),
        ),
        "japanese_bobtail": Breed(
            "Japanese Bobtail", "Japan",
            "Short-tailed cats have lived in Japan for centuries and appear in old woodblock prints. In "
            "1602 an edict ordered cats in Kyoto to be set free to protect silkworms from mice.",
            "The Kurilian Bobtail is another natural short-tailed cat from the region; the Manx's "
            "short tail comes from an unrelated gene.",
            (
                "Every Bobtail's tail is unique, kinked and curled like a pom-pom.",
                "The beckoning maneki-neko lucky cat is often said to be a Japanese Bobtail.",
            ),
            detectable=False,
        ),
        "persian": Breed(
            "Persian", "Iran",
            "Long-haired cats from Persia (today's Iran) reached Europe in the 1600s, brought by "
            "travellers such as Pietro della Valle. Queen Victoria kept Persians and made them "
            "fashionable. The very flat face seen today was bred much later, in the 20th century.",
            "The Exotic Shorthair is a short-haired Persian; the Himalayan is a colour-point Persian.",
            (
                "A Persian's long coat needs daily brushing — it can't keep it tidy alone.",
                "Very flat-faced Persians can have breathing and eye problems, so many breeders now "
                "aim for a gentler face.",
            ),
        ),
        "turkish_van": Breed(
            "Turkish Van", "Turkey",
            "From the Lake Van region of eastern Turkey, where such cats have lived for centuries. "
            "Two British travellers brought the first ones to Europe in 1955.",
            "Its pattern — white body, coloured head and tail — is called 'van pattern' in any breed.",
            (
                "Famous for enjoying water; locals call them swimming cats.",
                "Its coat has no woolly undercoat, so it feels like cashmere and dries quickly.",
            ),
            detectable=False,
        ),
        "turkish_angora": Breed(
            "Turkish Angora", "Turkey",
            "One of the oldest long-haired breeds, named after Ankara (once called Angora). Ankara Zoo "
            "has bred pure white Angoras since 1917 to keep the breed alive.",
            "Sometimes confused with the Persian, but slimmer, with a silky single coat.",
            (
                "Pure white Angoras with odd-coloured eyes are especially prized in Turkey.",
                "Its fine coat has no undercoat, so it hardly mats.",
            ),
            detectable=False,
        ),
        "aegean": Breed(
            "Aegean", "Greece",
            "A natural breed from Greece's Cyclades islands, where harbour cats have lived alongside "
            "fishermen for centuries. Greek breeders began developing it in the 1990s.",
            "It looks like many Mediterranean street cats — because that's exactly where it comes from.",
            (
                "Aegeans are said to like water and even catch fish in shallow harbours.",
                "Most are white with patches of one or two other colours.",
            ),
            detectable=False,
        ),
        "british_shorthair": Breed(
            "British Shorthair", "United Kingdom",
            "Descended from Britain's street and farm cats, possibly brought by the Romans. British "
            "Shorthairs were among the cats at the first modern cat show, London's Crystal Palace, 1871.",
            "The Scottish Fold is its folded-ear cousin; the Chartreux and Russian Blue look similar "
            "but are separate breeds.",
            (
                "The famous blue-grey 'British Blue' is only one of dozens of colours.",
                "The Cheshire Cat of Alice in Wonderland is often linked to its round, 'smiling' face.",
            ),
            # Downing Street's (non-pedigree) cats were all labelled British Shorthair.
            detectable=False,
        ),
        "scottish_fold": Breed(
            "Scottish Fold", "United Kingdom (Scotland)",
            "All Scottish Folds trace back to Susie, a white barn cat with folded ears found near Coupar "
            "Angus, Scotland, in 1961 by a shepherd called William Ross.",
            "Folds are crossed with British and American Shorthairs; kittens with straight ears are "
            "called Scottish Straights.",
            (
                "Kittens are born with straight ears; the fold appears at about three weeks.",
                "The gene that folds the ears affects cartilage everywhere and causes painful joint "
                "disease, so breeding Folds is banned or discouraged in several countries.",
            ),
            # The fold is too subtle for the model: British-looking street cats (Larry,
            # Gladstone) scored as Scottish Fold, while a real Fold scored only 0.59.
            detectable=False,
        ),
        "russian_blue": Breed(
            "Russian Blue", "Russia",
            "Said to come from the port of Arkhangelsk in northern Russia; sailors brought them to "
            "Britain, where they were shown at the Crystal Palace in 1875 as the 'Archangel Cat'.",
            "Often confused with the Korat, Chartreux and British Blue — look for its green eyes and "
            "slim, elegant build.",
            (
                "Its dense double coat stands out from the body like plush.",
                "Upturned mouth corners give it a slight 'smile'.",
            ),
            detectable=False,
        ),
        "siberian": Breed(
            "Siberian", "Russia",
            "Russia's native forest cat, living for centuries on farms and in villages near Siberian "
            "forests. The first breed standard was written in Russia in 1987; the first ones reached "
            "the USA in 1990.",
            "Close to the Norwegian Forest Cat and Maine Coon; its colour-point version is the Neva Masquerade.",
            (
                "Its three-layer coat is made for Siberian winters.",
                "Siberians tend to produce less of the main cat allergen, so some allergic people react "
                "less — but no cat is truly hypoallergenic.",
            ),
            detectable=False,
        ),
        "neva_masquerade": Breed(
            "Neva Masquerade", "Russia",
            "A colour-point Siberian developed in St Petersburg in the late 1980s and named after the "
            "city's Neva river.",
            "A Siberian by build, with the Siamese's colour points — a 'mask' on the face.",
            (
                "Like all colour-points, its mask darkens with age and in the cold.",
                "Its blue eyes are part of the breed standard.",
            ),
        ),
        "kurilian_bobtail": Breed(
            "Kurilian Bobtail", "Russia",
            "A natural bobtail from the Kuril Islands and Sakhalin, between Russia and Japan. Locals "
            "value it as a skilled mouser and even a fisher.",
            "Looks like a stockier, shaggier Japanese Bobtail.",
            (
                "No two tails are alike: each is a unique kinked pom-pom.",
                "Unusually for cats, many enjoy water.",
            ),
            detectable=False,
        ),
        "maine_coon": Breed(
            "Maine Coon", "USA",
            "One of the oldest natural breeds of North America, a working farm and ship's cat from Maine. "
            "A Maine Coon named Cosey won the first big US cat show, at Madison Square Garden in 1895.",
            "Looks like the Norwegian Forest Cat and Siberian. The old tale that it's part raccoon is "
            "genetically impossible.",
            (
                "One of the largest house-cat breeds; males can weigh over 8 kg.",
                "Big tufted paws work like snowshoes.",
            ),
        ),
        "american_shorthair": Breed(
            "American Shorthair", "USA",
            "Descends from cats that sailed with European settlers to guard ships and farms against "
            "rodents; recognised as a breed in the early 1900s.",
            "Compared with the British Shorthair it's lighter and longer-legged.",
            (
                "The classic silver tabby is its best-known look.",
                "It's one of the most popular pedigree cats in the USA.",
            ),
            detectable=False,
        ),
        "ragdoll": Breed(
            "Ragdoll", "USA",
            "Developed in California in the 1960s by breeder Ann Baker, starting from a white "
            "long-haired cat named Josephine.",
            "Looks like a larger Birman; both carry the colour-point gene.",
            (
                "Named for its habit of going limp when picked up.",
                "Kittens are born white and can take up to three years to reach full colour.",
            ),
        ),
        "sphynx": Breed(
            "Sphynx", "Canada",
            "Began with Prune, a hairless kitten born in Toronto in 1966 to an ordinary "
            "black-and-white cat.",
            "Russia's Donskoy and Peterbald are hairless too, but from a different gene.",
            (
                "Not truly bald: a fine down makes the skin feel like warm suede.",
                "With no fur to soak up skin oils, a Sphynx needs regular baths.",
            ),
        ),
        "bengal": Breed(
            "Bengal", "USA",
            "A hybrid of domestic cats and the wild Asian leopard cat, developed in the USA from the "
            "1970s by breeder Jean Mill.",
            "Its spots look like the Egyptian Mau's, but a Bengal's come from wild ancestry.",
            (
                "Many Bengals have 'glitter' — coat hairs that shimmer in the light.",
                "Pet Bengals are several generations away from the wild cat; early hybrids are "
                "restricted in some places.",
            ),
        ),
        "abyssinian": Breed(
            "Abyssinian", "Ethiopia (name) · Southeast Asia (genes)",
            "Named after Abyssinia (today's Ethiopia): a cat called Zula was brought to England from "
            "there in 1868. Genetic studies, though, point to origins around the Indian Ocean coast.",
            "The Somali is a long-haired Abyssinian.",
            (
                "Each hair is 'ticked' with bands of colour, giving a wild, rabbit-like shimmer.",
                "It resembles the cats painted in ancient Egyptian art.",
            ),
            detectable=False,
        ),
        "egyptian_mau": Breed(
            "Egyptian Mau", "Egypt",
            "One of the few naturally spotted domestic breeds. Modern Maus descend from cats taken from "
            "Cairo to Italy and then the USA in the 1950s by the exiled Russian princess Nathalie Troubetzkoy.",
            "Its spots are natural, unlike the hybrid Bengal's.",
            (
                "Among the fastest house cats — reportedly up to 48 km/h.",
                "'Mau' simply means 'cat' in ancient Egyptian.",
            ),
            detectable=False,
        ),
        "norwegian_forest": Breed(
            "Norwegian Forest Cat", "Norway",
            "The 'skogkatt' of Norwegian folk tales, possibly descended from cats that sailed with the "
            "Vikings. King Olav V made it Norway's official cat.",
            "Often confused with the Maine Coon and Siberian — look for its triangular face and "
            "straight profile.",
            (
                "Its water-repellent double coat was built for Nordic winters.",
                "It's said to climb down trees head-first, which most cats can't.",
            ),
            detectable=False,
        ),
        "exotic_shorthair": Breed(
            "Exotic Shorthair", "USA",
            "Created in the USA in the 1950s–60s by crossing Persians with American Shorthairs.",
            "A Persian in everything but coat length.",
            (
                "Nicknamed 'the lazy man's Persian' for its easy-care coat.",
                "Garfield is often said to look like one.",
            ),
        ),
        "devon_rex": Breed(
            "Devon Rex", "United Kingdom (England)",
            "Began with Kirlee, a curly-coated kitten found in Buckfastleigh, Devon, in 1960.",
            "Looks like the Cornish Rex, but its curls come from a different gene.",
            (
                "Big ears, huge eyes and a pixie face earned it the nickname 'pixie cat'.",
                "Its short wavy coat sheds less than most cats'.",
            ),
        ),
        "munchkin": Breed(
            "Munchkin", "USA",
            "Short-legged cats had been reported for decades, but the modern breed started with "
            "Blackberry, a cat found in Louisiana in 1983.",
            "Named after the Munchkins of The Wizard of Oz.",
            (
                "Its short legs come from a natural mutation; Munchkins still run and climb, just less high.",
                "The breed is controversial, and some cat registries don't recognise it.",
            ),
            detectable=False,
        ),
        "chartreux": Breed(
            "Chartreux", "France",
            "A sturdy blue-grey cat known in France for centuries; a popular legend links it to the "
            "Carthusian monks of the Grande Chartreuse monastery.",
            "Often confused with the British Blue and Russian Blue — look for its copper eyes and "
            "'smiling' face.",
            (
                "President Charles de Gaulle is said to have owned one.",
                "Its woolly coat is slightly water-repellent.",
            ),
            detectable=False,
        ),
        # Recognised only by the trained breed head (tools/train_breeds.py), so they have no
        # zero-shot prompt (detectable=False).
        "cornish_rex": Breed(
            "Cornish Rex", "United Kingdom (England)",
            "Began with Kallibunker, a curly-coated kitten born on a farm in Cornwall in 1950.",
            "Looks like the Devon Rex, but its curls come from a different gene; the German Rex "
            "carries the same gene as the Cornish.",
            (
                "Its coat has only the soft undercoat, without the usual guard hairs, so it feels like suede.",
                "Its arched back and long legs earned it the nickname 'the greyhound of cats'.",
            ),
            detectable=False,
        ),
        "donskoy": Breed(
            "Donskoy (Don Sphynx)", "Russia",
            "Began in Rostov-on-Don in 1987, when Elena Kovaleva rescued a kitten from boys "
            "teasing it; the kitten, Varvara, later lost her hair and passed it on to her kittens.",
            "Looks like the Canadian Sphynx, but its hairlessness comes from a different, "
            "dominant gene. The Peterbald descends from it.",
            (
                "Some Donskoy kittens are born bald; others lose their coat as they grow.",
                "Hairless cats feel warm to the touch and need protection from sun and cold.",
            ),
            detectable=False,
        ),
        "peterbald": Breed(
            "Peterbald", "Russia",
            "Bred in St Petersburg in 1994 by crossing a Donskoy with an Oriental Shorthair.",
            "A slender, Oriental-shaped cousin of the Donskoy; also mistaken for the Sphynx.",
            (
                "Its coat ranges from completely bald to short 'brush', and can change with age.",
                "It has the long legs, big ears and wedge-shaped head of Oriental cats.",
            ),
            detectable=False,
        ),
        "bombay": Breed(
            "Bombay", "USA",
            "Created in Kentucky in the 1950s by Nikki Horner, who crossed sable Burmese with black "
            "American Shorthairs to get a 'miniature panther'.",
            "Easily taken for an ordinary black cat — look for copper or gold eyes, a rounded head "
            "and a glossy, close-lying coat. Related to the Burmese.",
            (
                "Named after the Indian city of Bombay (Mumbai), a nod to the black leopards of India.",
                "Its short coat has a shine often compared to patent leather.",
            ),
            detectable=False,
        ),
        "burmilla": Breed(
            "Burmilla", "United Kingdom",
            "Began by accident in 1981, when a Chinchilla Persian and a lilac Burmese in the same "
            "household had kittens.",
            "Part Burmese, part Chinchilla Persian; the founding breed of the British 'Asian' group.",
            (
                "Its silver coat is tipped with colour, and its eyes look outlined with 'eyeliner'.",
                "There is also a semi-longhaired version, the Tiffanie.",
            ),
            detectable=False,
        ),
        "british_longhair": Breed(
            "British Longhair", "United Kingdom",
            "Long-haired kittens appeared in British Shorthair lines after they were crossed with "
            "Persians in the 20th century; breeders later kept them as a breed of their own.",
            "The long-haired sister of the British Shorthair; also resembles the Persian, but with "
            "a less flat face.",
            (
                "It has the British Shorthair's round face and sturdy body under a plush, half-long coat.",
                "Not every cat registry recognises it yet.",
            ),
            detectable=False,
        ),
        "oriental_longhair": Breed(
            "Oriental Longhair", "United Kingdom and USA",
            "Bred from Oriental Shorthairs crossed with long-haired cats; in Britain it was once "
            "called the British Angora.",
            "The long-haired Oriental Shorthair; like a Balinese, but in solid colours and patterns "
            "rather than colourpoint.",
            (
                "Its fine coat has little undercoat, so it lies close to the body.",
                "It comes in hundreds of colours and patterns.",
            ),
            detectable=False,
        ),
        "balinese": Breed(
            "Balinese", "USA",
            "Long-haired kittens occasionally appeared in Siamese litters; American breeders "
            "developed them from the 1950s. The name refers to the grace of Balinese dancers — "
            "the cats have nothing to do with Bali.",
            "The long-haired Siamese; some registries call its non-traditional colours 'Javanese'.",
            (
                "Its silky coat has no woolly undercoat, so it sheds less than it looks like it would.",
                "Like the Siamese, it is very talkative.",
            ),
            detectable=False,
        ),
        "thai": Breed(
            "Thai", "Thailand",
            "The old-style Siamese: when show Siamese were bred ever slimmer, some breeders kept "
            "the original rounder type, recognised in Europe as the Thai in 1990.",
            "Looks like the Siamese but with a rounder head and body — often called the "
            "'traditional' or 'apple-head' Siamese.",
            (
                "Pointed cats like it appear in the old Thai 'Cat Book Poems' manuscripts, as the Wichianmat.",
                "Its blue eyes and dark points come from the same gene as the Siamese.",
            ),
            detectable=False,
        ),
        "tonkinese": Breed(
            "Tonkinese", "Canada and USA",
            "Developed in the 1960s by crossing the Siamese with the Burmese.",
            "Halfway between its parents: a Siamese-like face with a Burmese body.",
            (
                "Its 'mink' coat shows points that blend softly into the body colour.",
                "Mink-coated Tonkinese often have striking aqua-coloured eyes.",
            ),
            detectable=False,
        ),
        "himalayan": Breed(
            "Himalayan", "USA and United Kingdom",
            "Bred from the 1930s by crossing Persians with Siamese, to get a Persian with "
            "colourpoint markings.",
            "A Persian in Siamese colours; in Britain it is called the Colourpoint Persian, and "
            "some registries count it as a Persian variety.",
            (
                "Named after the Himalayan rabbit, which has the same colourpoint pattern.",
                "It has the Persian's long coat and flat face, with blue eyes.",
            ),
            detectable=False,
        ),
        "snowshoe": Breed(
            "Snowshoe", "USA",
            "Began in Philadelphia in the 1960s, when a Siamese breeder got kittens with white feet "
            "and crossed them with bicolour American Shorthairs.",
            "A Siamese-coloured cat with white feet; often confused with the Ragdoll and Birman.",
            (
                "Named for its white 'boots'.",
                "Its pattern is hard to breed exactly, so no two Snowshoes look alike.",
            ),
            detectable=False,
        ),
        "savannah": Breed(
            "Savannah", "USA",
            "Began in 1986, when a male serval — a wild African cat — was crossed with a "
            "Siamese; the kitten was named Savannah.",
            "Part serval; looks like a small cheetah. Often confused with the Bengal, which has "
            "leopard-cat ancestry instead.",
            (
                "One of the tallest domestic cats, with very long legs and big ears.",
                "Early generations are restricted or banned as pets in some countries and US states.",
            ),
            detectable=False,
        ),
        "chausie": Breed(
            "Chausie", "USA",
            "Developed in the 1990s from crosses between domestic cats and the jungle cat, a wild "
            "cat of Asia and Egypt.",
            "Its name comes from the jungle cat's Latin name, Felis chaus; it looks like a large "
            "Abyssinian.",
            (
                "Long-legged and athletic, it is one of the larger domestic breeds.",
                "It comes only in black, silver-tipped black and brown ticked tabby.",
            ),
            detectable=False,
        ),
        "ocicat": Breed(
            "Ocicat", "USA",
            "Began in 1964 in Michigan, when a breeder crossing Abyssinians and Siamese got a "
            "spotted kitten, Tonga.",
            "Named after the wild ocelot it resembles, but it has no wild ancestry at all — only "
            "Abyssinian, Siamese and American Shorthair.",
            (
                "Its thumbprint-shaped spots run in rows along its body.",
                "It is known for being easy to train, even to walk on a lead.",
            ),
            detectable=False,
        ),
        "toyger": Breed(
            "Toyger", "USA",
            "Bred from the late 1980s by Judy Sugden, starting from a Bengal and a striped "
            "domestic cat, to create a 'toy tiger'.",
            "A striped relative of the Bengal; a mackerel tabby street cat can look similar, but "
            "the Toyger's stripes are bolder and branch like a tiger's.",
            (
                "Its breeder hoped a tiger-like pet would make people care about wild tigers.",
                "It has rounded ears and stripes even on its face.",
            ),
            detectable=False,
        ),
        "pixie_bob": Breed(
            "Pixie-bob", "USA",
            "Developed in the 1980s in Washington State from a bob-tailed cat named Pixie.",
            "Bred to look like a bobcat; legend says it has bobcat ancestry, but genetic tests "
            "show it is entirely domestic.",
            (
                "Many Pixie-bobs are polydactyl — they have extra toes.",
                "Its short tail and spotted coat give it a wild look.",
            ),
            detectable=False,
        ),
        "singapura": Breed(
            "Singapura", "Singapore",
            "Brought from Singapore to the USA in the 1970s; the exact story of its first cats "
            "has been disputed.",
            "Looks like a tiny Abyssinian: the same ticked coat, but in one sepia colour only.",
            (
                "One of the smallest cat breeds; adult females often weigh around 2 kg.",
                "Singapore once used it as a tourism mascot called Kucinta.",
            ),
            detectable=False,
        ),
        "somali": Breed(
            "Somali", "USA",
            "Long-haired kittens were sometimes born to Abyssinians; breeders developed them into "
            "a breed from the 1960s.",
            "The long-haired Abyssinian. Named after Somalia, the neighbour of Ethiopia — once "
            "called Abyssinia.",
            (
                "Its bushy tail has earned it the nickname 'fox cat'.",
                "Each hair has several bands of colour, like the Abyssinian's.",
            ),
            detectable=False,
        ),
        "asian": Breed(
            "Asian", "United Kingdom",
            "A British group of breeds that grew out of the Burmilla in the 1980s, keeping the "
            "Burmese body in new colours and patterns.",
            "Burmese-shaped cats in smoke, solid and tabby coats; the Burmilla and the Tiffanie "
            "belong to the same group.",
            (
                "It is recognised mainly by the British cat registry (GCCF).",
                "It has the Burmese's golden eyes and muscular body.",
            ),
            detectable=False,
        ),
        "tiffanie": Breed(
            "Tiffanie", "United Kingdom",
            "The semi-longhaired member of the British 'Asian' group, from the same Burmese × "
            "Chinchilla Persian beginnings as the Burmilla.",
            "A long-haired Burmilla or Asian; not the same as the American Chantilly-Tiffany.",
            (
                "Its silky coat ends in a plumed tail.",
                "It keeps the Burmese's rounded head and golden eyes.",
            ),
            detectable=False,
        ),
        "nebelung": Breed(
            "Nebelung", "USA",
            "Started in the 1980s by Cora Cobb from a long-haired blue cat, Siegfried, and his "
            "sister Brunhilde.",
            "A long-haired cat of Russian Blue type; its name echoes the German word for mist "
            "and the Nibelungenlied epic.",
            (
                "Its blue-grey coat is tipped with silver, which gives it a misty shine.",
                "It has green eyes, like the Russian Blue.",
            ),
            detectable=False,
        ),
        "manx": Breed(
            "Manx", "Isle of Man",
            "Tailless cats have lived on the Isle of Man for centuries; a folk tale says the Manx "
            "lost its tail when Noah shut the Ark's door on it.",
            "The Cymric is its long-haired version; other bob-tailed breeds get their short tails "
            "from different genes.",
            (
                "Some Manx have no tail at all ('rumpy'); others have a stub or even a full tail.",
                "The Manx cat has appeared on Isle of Man coins and stamps.",
            ),
            detectable=False,
        ),
        "selkirk_rex": Breed(
            "Selkirk Rex", "USA",
            "Began in Montana in 1987 with Miss DePesto, a curly-coated kitten born in a shelter.",
            "Its curls come from a dominant gene, unlike the Cornish and Devon Rex; it is sturdier "
            "and rounder, closer to a British Shorthair or Persian in build.",
            (
                "It comes in short and long coats, both curly — even the whiskers curl.",
                "Its coat is often compared to a lamb's fleece.",
            ),
            detectable=False,
        ),
        "american_curl": Breed(
            "American Curl", "USA",
            "Began in 1981 with Shulamith, a stray with backward-curling ears, adopted in "
            "Lakewood, California.",
            "Its ears curl back, while the Scottish Fold's fold forward.",
            (
                "Kittens are born with straight ears that curl within the first days of life.",
                "The curl comes from a natural mutation, not from crossing other breeds.",
            ),
            detectable=False,
        ),
        "mekong_bobtail": Breed(
            "Mekong Bobtail", "Southeast Asia and Russia",
            "Short-tailed colourpoint cats from Southeast Asia were developed into a breed by "
            "Russian breeders, and recognised by the WCF in 2004.",
            "Looks like a Thai (old-style Siamese) with a short, kinked tail.",
            (
                "Named after the Mekong River, which runs through the region it comes from.",
                "Its short tail is made of bent or fused vertebrae — no two are alike.",
            ),
            detectable=False,
        ),
    },
    Species.dog: {
        "labrador": Breed(
            "Labrador Retriever", "Canada · United Kingdom",
            "Descends from the St. John's water dogs of Newfoundland, which helped fishermen haul nets "
            "and fetch fish that slipped off the hooks. English nobles imported them in the 1800s and "
            "refined the breed in Britain.",
            "A cousin of the Golden, Flat-coated and Chesapeake Bay Retrievers.",
            (
                "Its thick 'otter tail' works as a rudder when swimming.",
                "Black, yellow and chocolate puppies can all be born in the same litter.",
            ),
        ),
        "golden_retriever": Breed(
            "Golden Retriever", "United Kingdom (Scotland)",
            "Developed in the Scottish Highlands in the 1860s by Lord Tweedmouth, starting with a "
            "yellow retriever called Nous and a Tweed Water Spaniel called Belle.",
            "A cousin of the Labrador and Flat-coated Retriever.",
            (
                "Its 'soft mouth' is said to carry an egg without breaking it.",
                "Goldens are among the world's most popular guide and therapy dogs.",
            ),
        ),
        "german_shepherd": Breed(
            "German Shepherd", "Germany",
            "Bred from Germany's old working sheepdogs. In 1899 cavalry officer Max von Stephanitz "
            "registered the first one, Horand von Grafrath, and set out to create the ideal herding "
            "dog; it soon became the world's classic police and service dog.",
            "A cousin — not a descendant — of the Belgian Malinois: both come from the herding dogs "
            "of 19th-century continental Europe and were developed at almost the same time.",
            (
                "In Britain it was renamed 'Alsatian' during the First World War to avoid the word 'German'.",
                "Rin Tin Tin, a puppy rescued from a First World War battlefield, became a Hollywood star.",
            ),
        ),
        "belgian_malinois": Breed(
            "Belgian Malinois", "Belgium",
            "One of four varieties of Belgian Shepherd, named after the city of Mechelen (Malines). "
            "Belgium's shepherd dogs were first described as a breed in 1891–1892 by Professor "
            "Adolphe Reul.",
            "A cousin of the German Shepherd, often mistaken for one: lighter, with a short fawn coat "
            "and a black mask.",
            (
                "Today it's the favourite dog of many police and military units worldwide.",
                "A Malinois named Cairo took part in the 2011 raid on Osama bin Laden's compound.",
            ),
            prompt_name="Belgian Malinois shepherd",
        ),
        "siberian_husky": Breed(
            "Siberian Husky", "Russia (Siberia)",
            "Bred by the Chukchi people of north-eastern Siberia to pull light sleds over long "
            "distances. Huskies came to Alaska in 1908 for sled races.",
            "Often confused with the bigger Alaskan Malamute; the Samoyed and Laika are fellow "
            "Siberian spitz dogs.",
            (
                "In the 1925 'serum run', sled teams carried diphtheria medicine to Nome, Alaska; lead "
                "dogs Togo and Balto became heroes.",
                "Blue eyes, brown eyes or one of each are all normal for Huskies.",
            ),
        ),
        "alaskan_malamute": Breed(
            "Alaskan Malamute", "USA (Alaska)",
            "An ancient freight sled dog of the Mahlemiut Inupiat people of Alaska, built for "
            "strength rather than speed.",
            "Bigger and heavier than the Siberian Husky, and always with brown eyes.",
            (
                "Malamutes hauled supplies for Richard Byrd's Antarctic expeditions.",
                "It's the official state dog of Alaska.",
            ),
        ),
        "samoyed": Breed(
            "Samoyed", "Russia (Siberia)",
            "Named after the Samoyedic peoples of Siberia, such as the Nenets, who used these white "
            "dogs to herd reindeer, pull sleds and keep warm at night.",
            "A Siberian spitz, like the Husky and the Laika.",
            (
                "Its upturned mouth — the 'Sammy smile' — is said to keep drool from freezing into icicles.",
                "Samoyeds pulled sledges on polar expeditions, including Roald Amundsen's journey to the South Pole.",
            ),
        ),
        "laika": Breed(
            "Laika", "Russia",
            "A family of Russian and Siberian hunting spitz dogs, such as the West and East Siberian "
            "Laika, used to hunt everything from squirrels to bears.",
            "A cousin of the Husky and Samoyed.",
            (
                "The space dog Laika, first animal to orbit the Earth in 1957, was actually a "
                "mixed-breed stray from the streets of Moscow.",
                "Laikas hunt by barking to hold game in place until the hunter arrives.",
            ),
            prompt_name="West Siberian Laika",
        ),
        "caucasian_shepherd": Breed(
            "Caucasian Shepherd", "Caucasus",
            "An ancient livestock guardian from the mountains of Georgia, Armenia, Azerbaijan and "
            "southern Russia, bred to protect flocks from wolves and bears.",
            "A cousin of the Central Asian Shepherd (Alabai) and Turkey's Kangal.",
            (
                "One of the largest dog breeds; males can weigh more than 70 kg.",
                "In East Germany these dogs patrolled the Berlin Wall.",
            ),
        ),
        "alabai": Breed(
            "Central Asian Shepherd (Alabai)", "Central Asia",
            "An ancient guardian of herds and caravans across Central Asia, shaped by nomads over "
            "thousands of years.",
            "A cousin of the Caucasian Shepherd and the Kangal.",
            (
                "In Turkmenistan the alabai is a national treasure with its own public holiday.",
                "A giant golden statue of an alabai stands in Ashgabat, Turkmenistan's capital.",
            ),
            prompt_name="Central Asian Shepherd dog",
        ),
        "kangal": Breed(
            "Kangal", "Turkey",
            "Turkey's national dog, a livestock guardian from Sivas province in central Anatolia, "
            "famous for protecting sheep from wolves.",
            "Often grouped with the Anatolian Shepherd and the white Akbash; many Turkish street dogs "
            "carry Kangal blood.",
            (
                "Its bite is often said to be among the strongest of all dogs.",
                "In Namibia and Kenya, Kangals guard herds from cheetahs — which also saves cheetahs "
                "from angry farmers.",
            ),
            prompt_name="Kangal Anatolian Shepherd dog",
        ),
        "shiba_inu": Breed(
            "Shiba Inu", "Japan",
            "The smallest of Japan's six native spitz breeds, an ancient mountain hunting dog. After "
            "the Second World War only three bloodlines survived; today's Shibas descend from them.",
            "Looks like a small Akita; the Korean Jindo is a similar-looking neighbour.",
            (
                "When unhappy, Shibas let out a piercing 'Shiba scream'.",
                "The 'Doge' meme made a Shiba named Kabosu one of the most famous dogs on Earth.",
            ),
        ),
        "akita": Breed(
            "Akita", "Japan",
            "From Akita prefecture in northern Japan, once a hunting dog, now a national monument of Japan.",
            "The American Akita is a heavier, separately bred version; the Shiba is its small cousin.",
            (
                "Hachikō waited for his late owner at Shibuya station every day for nearly ten years; "
                "his statue stands there today.",
                "Helen Keller brought the first Akita to the USA in 1937.",
            ),
        ),
        "jindo": Breed(
            "Korean Jindo", "South Korea",
            "From Jindo Island off south-west Korea; a national treasure of South Korea, protected by law.",
            "Looks like the Shiba and Akita, but developed independently in Korea.",
            (
                "In 1993 a Jindo named Baekgu, sold to a new owner, walked some 300 km back to her "
                "first home on the island.",
                "Jindos are famously loyal to a single person.",
            ),
        ),
        "phu_quoc_ridgeback": Breed(
            "Phu Quoc Ridgeback", "Vietnam",
            "From Phú Quốc island in southern Vietnam, a hunting and guard dog kept in isolation on "
            "the island for centuries.",
            "One of only three ridgeback breeds in the world, with the Thai and the Rhodesian Ridgeback.",
            (
                "Along its spine runs a ridge of hair growing the wrong way.",
                "Many have webbed feet and are strong swimmers.",
            ),
        ),
        "thai_ridgeback": Breed(
            "Thai Ridgeback", "Thailand",
            "An ancient hunting and guard dog of eastern Thailand, kept for centuries with little "
            "mixing with other breeds.",
            "A cousin of the Phu Quoc and Rhodesian Ridgebacks.",
            (
                "Its ridge comes in several shapes, from a simple stripe to a 'violin' or a 'feather'.",
                "It's an excellent jumper.",
            ),
        ),
        "hmong_dog": Breed(
            "H'Mông Dog", "Vietnam",
            "A bob-tailed dog of the H'Mông people in the mountains of northern Vietnam, used for "
            "hunting and guarding villages. The Vietnam Kennel Association recognises it as a national breed.",
            "Belongs to the same ancient Asian dog family as the region's village dogs.",
            (
                "Many are born with a naturally short tail.",
                "Nimble climbers, at home on steep mountain terraces.",
            ),
            prompt_name="H'Mong bobtail dog from Vietnam",
        ),
        "indian_pariah": Breed(
            "Indian Pariah Dog", "India",
            "The native street dog of the Indian subcontinent and one of the oldest dog types on "
            "Earth, shaped by natural selection rather than breeders.",
            "Part of the ancient 'village dog' family found across Asia and Africa.",
            (
                "Dogs like it appear in ancient Indian rock art.",
                "Hardy and street-smart, they rarely suffer the inherited diseases common in pedigree breeds.",
            ),
        ),
        "chihuahua": Breed(
            "Chihuahua", "Mexico",
            "Named after the Mexican state of Chihuahua; it probably descends from the Techichi, a "
            "small dog of the ancient Toltecs.",
            "The world's smallest dog breed.",
            (
                "Some Chihuahuas keep a soft spot on the skull for life, like a human baby's.",
                "A Chihuahua named Miracle Milly was the world's smallest living dog, under 10 cm tall.",
            ),
        ),
        "pit_bull": Breed(
            "American Pit Bull Terrier", "USA",
            "Descended from British bull-and-terrier dogs brought to the USA in the 1800s.",
            "Related to the American Staffordshire Terrier and the Staffordshire Bull Terrier.",
            (
                "In the early 1900s it was a popular American family dog.",
                "Many countries restrict it by law, though dog experts argue that upbringing matters "
                "more than breed.",
            ),
        ),
        "australian_shepherd": Breed(
            "Australian Shepherd", "USA",
            "Despite its name, it was developed on ranches in the western USA in the 1800s, possibly "
            "from dogs that arrived with sheep from Australia.",
            "A cousin of the Border Collie and other herding dogs.",
            (
                "Many have a marbled 'merle' coat and eyes of two different colours.",
                "Aussies became famous as rodeo performers in the 1950s.",
            ),
        ),
        "portuguese_water_dog": Breed(
            "Portuguese Water Dog", "Portugal",
            "A fishermen's dog that herded fish into nets, retrieved lost gear and swam messages "
            "between boats. It nearly vanished in the 1930s and was saved by the Portuguese shipping "
            "magnate Vasco Bensaude.",
            "Looks like a Poodle — both were water dogs — but it's a separate breed.",
            (
                "Bo and Sunny, the Obama family's dogs, were Portuguese Water Dogs.",
                "Its coat barely sheds.",
            ),
        ),
        "border_collie": Breed(
            "Border Collie", "United Kingdom",
            "A sheepdog from the border between England and Scotland; almost every modern Border "
            "Collie descends from Old Hemp, born in 1893.",
            "A cousin of the Australian Shepherd and other collies.",
            (
                "Often called the most intelligent of all dog breeds.",
                "A Border Collie named Chaser learned the names of over 1,000 toys.",
            ),
        ),
        "corgi": Breed(
            "Pembroke Welsh Corgi", "United Kingdom (Wales)",
            "A Welsh cattle dog that herded by nipping at heels, low enough to duck the kicks.",
            "The Cardigan Welsh Corgi is an older cousin with a long tail.",
            (
                "Queen Elizabeth II owned more than 30 corgis.",
                "Welsh legend says corgis carried fairy warriors; the saddle markings on their backs "
                "come from fairy saddles.",
            ),
        ),
        "poodle": Breed(
            "Poodle", "Germany · France",
            "Originally a German water retriever — the name comes from 'pudeln', to splash. It became "
            "so popular in France that it's now the French national dog.",
            "Comes in standard, miniature and toy sizes; crossbreeds like the Labradoodle inherit its "
            "low-shedding coat.",
            (
                "The famous poodle clip kept joints and chest warm in cold water while freeing the legs to swim.",
                "Poodles regularly rank among the most intelligent breeds.",
            ),
        ),
        "pomeranian": Breed(
            "Pomeranian", "Germany · Poland",
            "A small spitz named after Pomerania on the Baltic coast. Queen Victoria fell for small "
            "ones in Italy and made the toy size fashionable.",
            "A miniature of larger spitz dogs like the German Spitz.",
            (
                "Two Pomeranians survived the sinking of the Titanic in 1912.",
                "Early Pomeranians were much bigger — sheep-herding dogs of up to 14 kg.",
            ),
        ),
        "pug": Breed(
            "Pug", "China",
            "Kept in China for about 2,000 years as a companion of emperors. Dutch traders brought "
            "pugs to Europe in the 1500s, and they became a favourite of the royal House of Orange.",
            "Related to other Chinese flat-faced dogs like the Pekingese and Shih Tzu.",
            (
                "A pug named Pompey is said to have saved William of Orange by barking at approaching assassins.",
                "A group of pugs is called a 'grumble'.",
            ),
        ),
        "shih_tzu": Breed(
            "Shih Tzu", "China · Tibet",
            "A palace dog of the Chinese imperial court, with roots in Tibet. Its name means 'little lion'.",
            "Related to the Lhasa Apso and Pekingese.",
            (
                "After the Chinese empire fell the breed nearly vanished; today's Shih Tzus descend "
                "from about 14 dogs.",
                "Its long coat grows continuously, like human hair.",
            ),
        ),
        "french_bulldog": Breed(
            "French Bulldog", "France · England",
            "Small bulldogs came to France with English lace workers in the 1800s, and the bat-eared "
            "'Frenchie' was born in Paris.",
            "A small cousin of the English Bulldog.",
            (
                "Most Frenchies can't give birth naturally and are born by caesarean section.",
                "A French Bulldog named Gamin de Pycombe was lost on the Titanic.",
            ),
        ),
        "bulldog": Breed(
            "English Bulldog", "United Kingdom (England)",
            "Bred for bull-baiting, a blood sport banned in England in 1835; afterwards it was bred "
            "into a gentle companion.",
            "Ancestor of the French Bulldog, the Boston Terrier and many other bull breeds.",
            (
                "A symbol of British grit, often linked to Winston Churchill.",
                "Its flat face makes it prone to breathing problems in the heat.",
            ),
            prompt_name="English Bulldog",
        ),
        "beagle": Breed(
            "Beagle", "United Kingdom (England)",
            "An English scent hound bred to hunt hares in packs, followed by hunters on foot.",
            "A small cousin of the English Foxhound.",
            (
                "Its nose has around 220 million scent receptors; airports use Beagles to sniff out "
                "forbidden food in luggage.",
                "Snoopy from Peanuts is a Beagle.",
            ),
        ),
        "dachshund": Breed(
            "Dachshund", "Germany",
            "Its name means 'badger dog' in German: short legs and a long body let it follow badgers "
            "into their burrows.",
            "Comes in smooth, long-haired and wire-haired coats.",
            (
                "Waldi, a dachshund, was the first official Olympic mascot, at Munich 1972.",
                "Its loud bark was bred on purpose, so hunters could hear it underground.",
            ),
        ),
        "yorkshire_terrier": Breed(
            "Yorkshire Terrier", "United Kingdom (England)",
            "Bred in 19th-century Yorkshire to catch rats in textile mills and coal mines.",
            "Related to other small terriers such as the Skye Terrier.",
            (
                "A Yorkie named Smoky served with US soldiers in the Second World War.",
                "Its silky coat is closer to human hair than to typical dog fur.",
            ),
        ),
        "rottweiler": Breed(
            "Rottweiler", "Germany",
            "Thought to descend from the drovers' dogs of the Roman legions. In the German town of "
            "Rottweil it drove cattle to market; butchers are said to have tied their money pouches "
            "to its collar.",
            "A cousin of the Swiss mountain dogs such as the Bernese.",
            (
                "One of the first breeds used by German police.",
                "Its black-and-tan pattern is the same one the Dobermann has.",
            ),
        ),
        "dobermann": Breed(
            "Dobermann", "Germany",
            "Created in the 1890s by Louis Dobermann, a tax collector from Apolda, Germany, who wanted "
            "a protection dog on his rounds.",
            "Its ancestry probably includes the Rottweiler, German Pinscher and Manchester Terrier.",
            (
                "A Dobermann named Kurt was the first war dog killed in the 1944 battle for Guam; a war "
                "dog memorial there honours him.",
                "It's among the fastest-learning working dogs.",
            ),
            prompt_name="Doberman Pinscher",
        ),
        "boxer": Breed(
            "Boxer", "Germany",
            "Developed in 19th-century Germany from the Bullenbeisser, an older mastiff-type hunting dog.",
            "A cousin of the English Bulldog.",
            (
                "Its name is said to come from the way it spars with its front paws.",
                "Boxers were among the first police dogs in Germany.",
            ),
        ),
        "chow_chow": Breed(
            "Chow Chow", "China",
            "An ancient spitz from northern China, used as a guard, hunter and cart dog.",
            "Genetically one of the oldest breeds; it shares its blue-black tongue with the Shar Pei.",
            (
                "Its straight hind legs give it a stiff, stilted walk.",
                "Its lion-like mane made it a favourite of Queen Victoria.",
            ),
        ),
        "shar_pei": Breed(
            "Shar Pei", "China",
            "A wrinkled guard and hunting dog from southern China.",
            "The only other breed with a blue-black tongue, like the Chow Chow.",
            (
                "In 1978 Guinness listed it as the rarest dog breed in the world.",
                "Its name means 'sand skin', for its rough coat.",
            ),
        ),
        "maltese": Breed(
            "Maltese", "Mediterranean",
            "One of the oldest toy breeds, a lap dog of the ancient Mediterranean linked to the island of Malta.",
            "Related to the Bichon Frise and the Havanese.",
            (
                "Ancient Greeks and Romans kept them; they appear on Greek pottery.",
                "It has no undercoat and sheds very little.",
            ),
        ),
        "jack_russell": Breed(
            "Jack Russell Terrier", "United Kingdom (England)",
            "Named after the Reverend John Russell, who bred small white terriers for fox hunting in the 1800s.",
            "Close to the Parson Russell Terrier.",
            (
                "A Jack Russell named Moose played Eddie on the TV show Frasier.",
                "Bred to chase foxes out of burrows, it has seemingly endless energy.",
            ),
        ),
        "dalmatian": Breed(
            "Dalmatian", "Croatia",
            "Named after Dalmatia on the Croatian coast. In England it became a carriage dog, running "
            "beside coaches, and later ran with horse-drawn fire engines.",
            "No close look-alikes — its spots are one of a kind.",
            (
                "Puppies are born pure white; the spots appear over the first weeks.",
                "Dalmatians are the mascot of many fire stations, especially in the USA.",
            ),
        ),
        "great_dane": Breed(
            "Great Dane", "Germany",
            "Despite the name, a German breed, developed as a boar-hunting and estate guard dog.",
            "A giant cousin of the mastiffs.",
            (
                "A Great Dane named Zeus was the tallest dog ever recorded, 111.8 cm at the shoulder.",
                "Scooby-Doo is a Great Dane.",
            ),
        ),
        "saint_bernard": Breed(
            "Saint Bernard", "Switzerland",
            "The rescue dog of the Great St Bernard Pass hospice in the Swiss Alps, where monks used "
            "it to find travellers lost in the snow.",
            "A cousin of the Swiss mountain dogs.",
            (
                "The most famous, Barry, is credited with saving more than 40 people; he's preserved "
                "in the Natural History Museum in Bern.",
                "The little brandy barrel on its collar is a myth made popular by a painting.",
            ),
        ),
        "rhodesian_ridgeback": Breed(
            "Rhodesian Ridgeback", "Southern Africa",
            "Bred in southern Africa by crossing European dogs with the ridged hunting dogs of the "
            "Khoikhoi people; used to track lions and hold them at bay.",
            "Shares its backward-growing hair ridge with the Thai and Phu Quoc Ridgebacks.",
            (
                "It was once called the 'African Lion Hound'.",
                "Its ridge is formed by two whorls of hair called 'crowns'.",
            ),
        ),
        "cane_corso": Breed(
            "Cane Corso", "Italy",
            "An Italian mastiff descended from Roman war dogs, used to guard farms and hunt boar. It "
            "was rescued from near extinction in the 1970s.",
            "A cousin of the Neapolitan Mastiff.",
            (
                "Its name roughly means 'guardian dog' in Italian.",
                "It was one of the few breeds kept by Italian farmers well into the 20th century.",
            ),
        ),
        "spitz": Breed(
            "Japanese Spitz", "Japan",
            "A fluffy white companion developed in Japan in the 1920s–30s from white German spitz dogs.",
            "Looks like a small Samoyed or a white Pomeranian.",
            (
                "Despite its bright white coat, it stays clean easily: dry dirt tends to fall out.",
                "It's one of the most popular companion dogs in Japan.",
            ),
        ),
    },
}


# Wikidata ids of our breeds: the trained breed head (tools/train_breeds.py) predicts these.
WIKIDATA: dict[Species, dict[str, str]] = {
    Species.cat: {
        "siamese": "Q42604", "oriental_shorthair": "Q42696", "havana_brown": "Q42645",
        "khao_manee": "Q42700", "korat": "Q42691", "birman": "Q42563", "burmese": "Q42573",
        "japanese_bobtail": "Q42673", "persian": "Q42610", "turkish_van": "Q42724",
        "turkish_angora": "Q42720", "aegean": "Q7957", "british_shorthair": "Q29273",
        "scottish_fold": "Q42636", "russian_blue": "Q42654", "siberian": "Q42630",
        "neva_masquerade": "Q42599", "kurilian_bobtail": "Q7338", "maine_coon": "Q42659",
        "american_shorthair": "Q7962", "ragdoll": "Q42688", "sphynx": "Q42712",
        "bengal": "Q42583", "abyssinian": "Q7955", "egyptian_mau": "Q7295",
        "norwegian_forest": "Q42667", "exotic_shorthair": "Q42555", "devon_rex": "Q42570",
        "munchkin": "Q686698", "chartreux": "Q42588",
        "cornish_rex": "Q42559", "donskoy": "Q7303", "peterbald": "Q42663", "bombay": "Q42566",
        "burmilla": "Q29258", "british_longhair": "Q29268", "oriental_longhair": "Q2099338",
        "balinese": "Q9665", "thai": "Q42732", "tonkinese": "Q42726", "himalayan": "Q42959",
        "snowshoe": "Q42633", "savannah": "Q42670", "chausie": "Q42546", "ocicat": "Q42685",
        "toyger": "Q7323", "pixie_bob": "Q42693", "singapura": "Q42679", "somali": "Q42715",
        "asian": "Q7974", "tiffanie": "Q7986", "nebelung": "Q42647", "manx": "Q42675",
        "selkirk_rex": "Q42642", "american_curl": "Q7960", "mekong_bobtail": "Q16889346",
    },
    Species.dog: {},
}


@lru_cache
def _breed_clip() -> tuple[CLIPModel, CLIPProcessor]:
    """Breeds need a larger CLIP than species/coat: fine details decide between look-alikes."""
    if settings.breed_clip_model == settings.clip_model:
        clip = get_classifier()
        return clip.model, clip.processor
    return (
        CLIPModel.from_pretrained(settings.breed_clip_model).eval(),
        CLIPProcessor.from_pretrained(settings.breed_clip_model),
    )


def _detectable(species: Species) -> list[str]:
    return [k for k, b in BREEDS[species].items() if b.detectable]


@lru_cache
def _breed_zero_shot(species: Species) -> ZeroShot:
    model, processor = _breed_clip()
    prompts = [
        f"a photo of a {BREEDS[species][k].prompt_name or BREEDS[species][k].label}, a type of {species.value}."
        for k in _detectable(species)
    ]
    return ZeroShot(model, processor, prompts + MIXED_PROMPTS[species])


def breed_scores(
    image: Image.Image, species: Species, features: torch.Tensor | None = None
) -> tuple[list[tuple[str, float]], float]:
    """Detectable breeds ranked by probability, and the total probability of "mixed breed"."""
    keys = _detectable(species)
    probs = _breed_zero_shot(species).probs(image, features)
    ranked = sorted(zip(keys, probs[: len(keys)]), key=lambda kv: kv[1], reverse=True)
    return ranked, sum(probs[len(keys):])


class Certainty(str, enum.Enum):
    confirmed = "confirmed"  # "Siamese"
    likely = "likely"  # "Looks like a Siamese"
    maybe = "maybe"  # "Maybe a Birman or a Himalayan": a guess, clearly worded as one
    mixed = "mixed"  # "Probably a mixed breed": no breed key


class Verdict(NamedTuple):
    """What the card says about the breed. `key` is None for mixed; `alt` is the second
    guess of a "maybe"."""
    key: str | None
    certainty: Certainty
    alt: str | None = None


def decide_breed(
    ranked: list[tuple[str, float]], mixed: float, species: Species
) -> tuple[str, Certainty] | None:
    """The breed and how sure we are, or None for "breed unknown". Never beats "mixed"."""
    key, prob = ranked[0]
    if prob <= mixed:
        return None
    if prob >= settings.breed_min_confidence[species.value]:
        return key, Certainty.confirmed
    if prob >= settings.breed_likely_confidence[species.value]:
        return key, Certainty.likely
    return None


HEADS = Path(__file__).parent / "breed_heads"


@lru_cache
def _breed_head(species: Species) -> dict | None:
    """The trained classifier for this species (tools/train_breeds.py), if there is one."""
    path = HEADS / f"{species.value}.pt"
    return torch.load(path, weights_only=True) if path.exists() else None


# Look-alikes the head splits unreliably (Siamese vs its descendants and relatives): when
# none of them is likely enough alone but together they are, the card says "Looks like a
# Siamese". On held-out photos this added 5 right answers and no wrong ones.
FAMILIES: dict[Species, dict[str, list[str]]] = {
    Species.cat: {"siamese": ["siamese", "thai", "tonkinese", "balinese", "snowshoe", "mekong_bobtail"]},
    Species.dog: {},
}


def head_probs(features: torch.Tensor, species: Species) -> dict[str, float]:
    """Probability per class of the trained head: our breed keys, "mixed", and Wikidata ids of
    breeds we have no card for (they still help, as a class to pick instead of a look-alike)."""
    head = _breed_head(species)
    probs = (features[0] * 10 @ head["weight"].T + head["bias"]).softmax(-1)
    to_key = {qid: k for k, qid in WIKIDATA[species].items()}
    return {to_key.get(c, c): float(p) for c, p in zip(head["classes"], probs)}


def decide_head_breed(probs: dict[str, float], mixed: float, species: Species) -> Verdict | None:
    """The head's verdict, or None for "breed unknown". `mixed` is zero-shot's probability of
    "mixed breed": above the veto the animal is called mixed, however sure the head is."""
    key, prob = max(probs.items(), key=lambda kv: kv[1])
    if mixed >= settings.breed_head_mixed_veto or key == "mixed":
        return Verdict(None, Certainty.mixed)
    if key in BREEDS[species]:
        if prob >= settings.breed_head_confirmed:
            return Verdict(key, Certainty.confirmed)
        if prob >= settings.breed_head_likely:
            return Verdict(key, Certainty.likely)
    for name, members in FAMILIES[species].items():
        if sum(probs.get(m, 0.0) for m in members) >= settings.breed_head_likely:
            return Verdict(name, Certainty.likely)
    # Not sure, but not clueless: name the best one or two guesses, worded as guesses.
    guesses = [k for k, p in sorted(probs.items(), key=lambda kv: -kv[1])
               if k in BREEDS[species] and p >= settings.breed_head_maybe][:2]
    return Verdict(guesses[0], Certainty.maybe, *guesses[1:]) if guesses else None


@torch.inference_mode()
def detect_breed(image: Image.Image, species: Species) -> Verdict | None:
    """Breed of the animal in `image`, which should be cropped to the animal."""
    if _breed_head(species) is None:
        ranked, mixed = breed_scores(image, species)
        claim = decide_breed(ranked, mixed, species)
        return Verdict(*claim) if claim else None
    features = _breed_zero_shot(species).image_features(image)
    _, mixed = breed_scores(image, species, features)
    return decide_head_breed(head_probs(features, species), mixed, species)
