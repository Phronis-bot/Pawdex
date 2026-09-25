"""Breeds: detected with CLIP zero-shot, but only when the model is confident.

Most street animals are mixed, so "mixed breed" competes with every breed and wins
ties. A breed never changes rarity (that is by coat), and it is shown only on the
animal's card, never on the map: purebred animals are the ones that get stolen.
"""
from dataclasses import dataclass
from functools import lru_cache

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from app.classifier import get_classifier
from app.config import settings
from app.models import Species


@dataclass(frozen=True)
class Breed:
    label: str
    origin: str
    history: str
    # CLIP prompt name when the label alone is ambiguous.
    prompt_name: str | None = None
    # False for breeds that look like ordinary street animals (e.g. American Shorthair):
    # the model can't tell them apart reliably, so we never claim them.
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
            "One of the oldest known breeds: pointed cats appear in the Tamra Maew, old cat poems "
            "from Siam (today's Thailand). They reached Europe and America in the 1870s–1880s.",
        ),
        "khao_manee": Breed(
            "Khao Manee", "Thailand",
            "An all-white Thai cat whose name means 'white gem'. It is also described in the "
            "Tamra Maew and often has eyes of two different colours.",
            detectable=False,
        ),
        "korat": Breed(
            "Korat", "Thailand",
            "A silver-blue cat from north-eastern Thailand, traditionally a symbol of good luck "
            "and given as a wedding gift.",
            detectable=False,
        ),
        "birman": Breed(
            "Birman", "Myanmar (legend) · France",
            "Linked by legend to temples of Burma, the breed was developed in France in the 1920s. "
            "Look for its white 'gloves' on all four paws.",
        ),
        "burmese": Breed(
            "Burmese", "Myanmar · USA",
            "Almost every Burmese descends from Wong Mau, a brown cat brought from Burma to the "
            "United States in 1930.",
        ),
        "japanese_bobtail": Breed(
            "Japanese Bobtail", "Japan",
            "Known in Japan for centuries, with a short pom-pom tail. The beckoning 'maneki-neko' "
            "lucky cat is often said to be one.",
            detectable=False,
        ),
        "persian": Breed(
            "Persian", "Iran",
            "Long-haired cats from Persia reached Europe in the 1600s. Today's flat-faced look was "
            "bred much later, in the 20th century.",
        ),
        "turkish_van": Breed(
            "Turkish Van", "Turkey",
            "From the Lake Van region of eastern Turkey. Mostly white with colour on the head and "
            "tail, and famous for actually enjoying water.",
            detectable=False,
        ),
        "turkish_angora": Breed(
            "Turkish Angora", "Turkey",
            "One of the oldest long-haired breeds, from the Ankara region. Ankara Zoo has run a "
            "breeding programme for pure white Angoras since 1917.",
            detectable=False,
        ),
        "aegean": Breed(
            "Aegean", "Greece",
            "A natural breed from Greece's Cyclades islands: harbour cats long used to living on "
            "fishermen's scraps.",
            detectable=False,
        ),
        "british_shorthair": Breed(
            "British Shorthair", "United Kingdom",
            "Descended from Britain's street and farm cats. British Shorthairs were among the cats "
            "at the first modern cat show, held in London in 1871.",
            # Downing Street's (non-pedigree) cats were all labelled British Shorthair.
            detectable=False,
        ),
        "scottish_fold": Breed(
            "Scottish Fold", "United Kingdom (Scotland)",
            "All Scottish Folds trace back to Susie, a farm cat found in Scotland in 1961. The gene "
            "that folds the ears also affects cartilage and can cause painful joint disease.",
        ),
        "russian_blue": Breed(
            "Russian Blue", "Russia",
            "Said to come from the port of Arkhangelsk; it was shown in England in 1875 as the "
            "'Archangel Cat'. Its short coat is silvery blue-grey.",
            detectable=False,
        ),
        "siberian": Breed(
            "Siberian", "Russia",
            "Russia's native forest cat, with a thick three-layer coat made for Siberian winters.",
            detectable=False,
        ),
        "neva_masquerade": Breed(
            "Neva Masquerade", "Russia",
            "A colour-point Siberian developed in St Petersburg and named after the Neva river.",
        ),
        "kurilian_bobtail": Breed(
            "Kurilian Bobtail", "Russia",
            "A natural bobtail from the Kuril Islands and Sakhalin, with a short fluffy tail like a pom-pom.",
            detectable=False,
        ),
        "maine_coon": Breed(
            "Maine Coon", "USA",
            "One of the largest house cats, a working farm cat from the north-eastern United States "
            "and the official state cat of Maine.",
        ),
        "american_shorthair": Breed(
            "American Shorthair", "USA",
            "Descends from cats that sailed with European settlers to keep ships and farms free of rodents.",
            detectable=False,
        ),
        "ragdoll": Breed(
            "Ragdoll", "USA",
            "Developed in California in the 1960s; named for its habit of going limp when picked up.",
        ),
        "sphynx": Breed(
            "Sphynx", "Canada",
            "The breed began with a hairless kitten born in Toronto in 1966. It isn't truly bald: "
            "a fine down covers the skin.",
        ),
        "bengal": Breed(
            "Bengal", "USA",
            "A hybrid of domestic cats and the wild Asian leopard cat, developed in the United "
            "States from the 1970s — hence the wild-looking spots.",
        ),
        "abyssinian": Breed(
            "Abyssinian", "Ethiopia (name) · Southeast Asia (genes)",
            "Named after Abyssinia (today's Ethiopia): a cat called Zula was brought to England from "
            "there in 1868. Genetic studies, though, point to origins around the Indian Ocean coast.",
            detectable=False,
        ),
        "egyptian_mau": Breed(
            "Egyptian Mau", "Egypt",
            "One of the few naturally spotted domestic breeds, and among the fastest runners of all house cats.",
            detectable=False,
        ),
        "norwegian_forest": Breed(
            "Norwegian Forest Cat", "Norway",
            "The 'skogkatt' of Norwegian folk tales, with a thick water-repellent coat for Nordic winters.",
            detectable=False,
        ),
        "exotic_shorthair": Breed(
            "Exotic Shorthair", "USA",
            "A Persian crossed with shorter-haired cats in the 1960s: all the Persian's looks with an "
            "easy-care coat, nicknamed 'the Persian in pyjamas'.",
        ),
        "devon_rex": Breed(
            "Devon Rex", "United Kingdom (England)",
            "Began with a curly-coated kitten found in Devon in 1960. Wavy fur, big ears, pixie face.",
        ),
        "munchkin": Breed(
            "Munchkin", "USA",
            "Its short legs come from a natural mutation; the modern breed started with a cat found "
            "in Louisiana in 1983.",
            detectable=False,
        ),
        "chartreux": Breed(
            "Chartreux", "France",
            "A sturdy blue-grey French cat; a popular legend links it to the Carthusian monks.",
            detectable=False,
        ),
    },
    Species.dog: {
        "labrador": Breed(
            "Labrador Retriever", "Canada · United Kingdom",
            "Descends from the St. John's water dogs of Newfoundland that helped fishermen haul "
            "nets; the breed was refined in Britain in the 1800s.",
        ),
        "golden_retriever": Breed(
            "Golden Retriever", "United Kingdom (Scotland)",
            "Developed in the Scottish Highlands in the 1860s by Lord Tweedmouth as a gun dog "
            "that could retrieve from water and land.",
        ),
        "german_shepherd": Breed(
            "German Shepherd", "Germany",
            "Created in 1899 by cavalry officer Max von Stephanitz as the ideal herding dog; it "
            "soon became the world's classic police and service dog.",
        ),
        "siberian_husky": Breed(
            "Siberian Husky", "Russia (Siberia)",
            "Bred by the Chukchi people of north-eastern Siberia as sled dogs. Huskies became famous "
            "in the 1925 'serum run' carrying diphtheria medicine to Nome, Alaska.",
        ),
        "alaskan_malamute": Breed(
            "Alaskan Malamute", "USA (Alaska)",
            "A heavy freight sled dog of the Mahlemiut Inuit of Alaska, built for strength rather than speed.",
        ),
        "samoyed": Breed(
            "Samoyed", "Russia (Siberia)",
            "Named after the Samoyedic peoples of Siberia, who used these white dogs to herd reindeer "
            "and pull sledges. Their upturned mouth is the 'Sammy smile'.",
        ),
        "laika": Breed(
            "Laika", "Russia",
            "A family of Russian hunting spitz dogs. The famous space dog Laika, first animal to "
            "orbit the Earth in 1957, was actually a mixed-breed stray from the streets of Moscow.",
            prompt_name="West Siberian Laika",
        ),
        "caucasian_shepherd": Breed(
            "Caucasian Shepherd", "Caucasus",
            "A huge livestock guardian from the mountains of Georgia, Armenia, Azerbaijan and southern "
            "Russia, bred to protect flocks from wolves.",
        ),
        "alabai": Breed(
            "Central Asian Shepherd (Alabai)", "Central Asia",
            "An ancient guardian of herds across Central Asia. In Turkmenistan the alabai is a "
            "national treasure with its own public holiday.",
            prompt_name="Central Asian Shepherd dog",
        ),
        "kangal": Breed(
            "Kangal", "Turkey",
            "Turkey's national dog, a livestock guardian from Sivas province with a black mask, "
            "famous for protecting sheep from wolves.",
            prompt_name="Kangal Anatolian Shepherd dog",
        ),
        "shiba_inu": Breed(
            "Shiba Inu", "Japan",
            "The smallest of Japan's native spitz breeds, an ancient mountain hunting dog. It nearly "
            "disappeared after the Second World War.",
        ),
        "akita": Breed(
            "Akita", "Japan",
            "From Akita prefecture in northern Japan. The most famous Akita, Hachikō, waited for his "
            "late owner at Shibuya station every day for nearly ten years.",
        ),
        "jindo": Breed(
            "Korean Jindo", "South Korea",
            "From Jindo Island, a national treasure of Korea known for loyalty: in 1993 a Jindo named "
            "Baekgu walked some 300 km back to her first home on the island.",
        ),
        "phu_quoc_ridgeback": Breed(
            "Phu Quoc Ridgeback", "Vietnam",
            "From Phú Quốc island. Along its back runs a ridge of hair growing the wrong way — it is "
            "one of only three ridgeback breeds in the world.",
        ),
        "thai_ridgeback": Breed(
            "Thai Ridgeback", "Thailand",
            "An ancient Thai hunting and guard dog, with a ridge of backward-growing hair along its spine.",
        ),
        "hmong_dog": Breed(
            "H'Mông Dog", "Vietnam",
            "A bob-tailed dog of the H'Mông people in the mountains of northern Vietnam, "
            "traditionally used for hunting and guarding.",
            prompt_name="H'Mong bobtail dog from Vietnam",
        ),
        "indian_pariah": Breed(
            "Indian Pariah Dog", "India",
            "The native street dog of India and one of the oldest dog types on Earth, shaped by "
            "natural selection rather than breeders.",
        ),
        "chihuahua": Breed(
            "Chihuahua", "Mexico",
            "The world's smallest breed, named after the Mexican state of Chihuahua; it probably "
            "descends from the ancient Techichi dogs of Mexico.",
        ),
        "pit_bull": Breed(
            "American Pit Bull Terrier", "USA",
            "Descended from British bull-and-terrier dogs brought to the United States in the 1800s.",
        ),
        "australian_shepherd": Breed(
            "Australian Shepherd", "USA",
            "Despite its name, it was developed on ranches in the western United States.",
        ),
        "portuguese_water_dog": Breed(
            "Portuguese Water Dog", "Portugal",
            "A fishermen's dog that herded fish into nets, retrieved lost gear and swam messages "
            "between boats. Bo and Sunny, the Obama family's dogs, were Portuguese Water Dogs.",
        ),
        "border_collie": Breed(
            "Border Collie", "United Kingdom",
            "A sheepdog from the border between England and Scotland, often called the most "
            "intelligent of all dog breeds.",
        ),
        "corgi": Breed(
            "Pembroke Welsh Corgi", "United Kingdom (Wales)",
            "A Welsh cattle dog that herded by nipping at heels. Queen Elizabeth II owned more "
            "than 30 of them.",
        ),
        "poodle": Breed(
            "Poodle", "Germany · France",
            "Originally a German water retriever — 'Pudel' comes from a word for splashing — and "
            "today the national dog of France.",
        ),
        "pomeranian": Breed(
            "Pomeranian", "Germany · Poland",
            "A small spitz named after Pomerania on the Baltic coast; Queen Victoria made the tiny version fashionable.",
        ),
        "pug": Breed(
            "Pug", "China",
            "Kept in China for about 2,000 years; Dutch traders brought pugs to Europe in the 1500s.",
        ),
        "shih_tzu": Breed(
            "Shih Tzu", "China · Tibet",
            "A palace dog of the Chinese imperial court, with roots in Tibet. The name means 'little lion'.",
        ),
        "french_bulldog": Breed(
            "French Bulldog", "France · England",
            "Small bulldogs came to France with English lace workers in the 1800s, where the "
            "bat-eared 'Frenchie' was born.",
        ),
        "bulldog": Breed(
            "English Bulldog", "United Kingdom (England)",
            "Once bred for bull-baiting, a blood sport banned in England in 1835; later bred into a "
            "gentle companion.",
            prompt_name="English Bulldog",
        ),
        "beagle": Breed(
            "Beagle", "United Kingdom (England)",
            "An English scent hound bred to hunt hares in packs; its nose has around 220 million scent receptors.",
        ),
        "dachshund": Breed(
            "Dachshund", "Germany",
            "Its name means 'badger dog': short legs and a long body let it follow badgers into their burrows.",
        ),
        "yorkshire_terrier": Breed(
            "Yorkshire Terrier", "United Kingdom (England)",
            "Bred in 19th-century Yorkshire to catch rats in textile mills and coal mines.",
        ),
        "rottweiler": Breed(
            "Rottweiler", "Germany",
            "From the German town of Rottweil, where it drove cattle to market; butchers are said "
            "to have tied their money pouches to its collar.",
        ),
        "dobermann": Breed(
            "Dobermann", "Germany",
            "Created in the 1890s by Louis Dobermann, a tax collector who wanted a protection dog on his rounds.",
            prompt_name="Doberman Pinscher",
        ),
        "boxer": Breed(
            "Boxer", "Germany",
            "Developed in 19th-century Germany from older mastiff-type hunting dogs.",
        ),
        "chow_chow": Breed(
            "Chow Chow", "China",
            "An ancient Chinese spitz with a lion-like mane and a blue-black tongue.",
        ),
        "shar_pei": Breed(
            "Shar Pei", "China",
            "A wrinkled guard dog from southern China; in the 1970s it was one of the rarest breeds in the world.",
        ),
        "maltese": Breed(
            "Maltese", "Mediterranean",
            "One of the oldest toy breeds, a lap dog of the ancient Mediterranean linked to the island of Malta.",
        ),
        "jack_russell": Breed(
            "Jack Russell Terrier", "United Kingdom (England)",
            "Named after the Reverend John Russell, who bred small white terriers for fox hunting in the 1800s.",
        ),
        "dalmatian": Breed(
            "Dalmatian", "Croatia",
            "Named after Dalmatia on the Adriatic coast and once a carriage dog running beside "
            "coaches. Puppies are born pure white; the spots come later.",
        ),
        "great_dane": Breed(
            "Great Dane", "Germany",
            "Despite the name, a German breed, developed as a boar-hunting and estate dog.",
        ),
        "saint_bernard": Breed(
            "Saint Bernard", "Switzerland",
            "The rescue dog of the Great St Bernard Pass hospice in the Alps. The most famous, "
            "Barry, is credited with saving more than 40 people.",
        ),
        "rhodesian_ridgeback": Breed(
            "Rhodesian Ridgeback", "Southern Africa",
            "Bred in southern Africa to track lions and hold them at bay; it shares the backward "
            "hair ridge with the Thai and Phu Quoc ridgebacks.",
        ),
        "cane_corso": Breed(
            "Cane Corso", "Italy",
            "An Italian mastiff that guarded farms and hunted boar; the breed was rescued from near "
            "extinction in the 1970s.",
        ),
        "spitz": Breed(
            "Japanese Spitz", "Japan",
            "A fluffy white companion spitz developed in Japan in the 20th century.",
        ),
    },
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


@torch.inference_mode()
def breed_scores(image: Image.Image, species: Species) -> tuple[list[tuple[str, float]], float]:
    """Detectable breeds ranked by probability, and the total probability of "mixed breed"."""
    model, processor = _breed_clip()
    breeds = {k: b for k, b in BREEDS[species].items() if b.detectable}
    prompts = [f"a photo of a {b.prompt_name or b.label}, a type of {species.value}." for b in breeds.values()]
    inputs = processor(text=prompts + MIXED_PROMPTS[species], images=image, return_tensors="pt", padding=True)
    probs = model(**inputs).logits_per_image.softmax(dim=-1)[0].tolist()
    ranked = sorted(zip(breeds, probs[: len(breeds)]), key=lambda kv: kv[1], reverse=True)
    return ranked, sum(probs[len(breeds):])


def detect_breed(image: Image.Image, species: Species) -> str | None:
    """A breed key only when CLIP is confident and it beats "mixed breed"; otherwise None."""
    ranked, mixed = breed_scores(image, species)
    key, prob = ranked[0]
    threshold = settings.breed_min_confidence[species.value]
    if prob >= threshold and prob > mixed:
        return key
    return None
