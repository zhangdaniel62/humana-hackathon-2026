"""Hand-authored language maps over the 20 CPT codes in coverage_rules.csv.

Why hand-authored rather than fuzzy matching: the code set is tiny (20), closed,
and known at author time. Fuzzy scoring over 20 items has no ground truth to tune
against -- at any cutoff loose enough to catch real paraphrases, difflib matches
"colonoscopy" to "Total Knee Arthroplasty". A map is deterministic, reviewable,
dependency-free, and -- decisively -- lets ambiguity be *declared* rather than
discovered by a threshold.

ALIASES resolve to exactly one code. AMBIGUITY_GROUPS are colloquial phrases that
genuinely name more than one service; they are answered with a question, never a
guess. Canonical CSV descriptions are added to the index automatically by kb.py.
"""

# phrase -> single CPT code
ALIASES: dict[str, tuple[str, ...]] = {
    "27447": ("total knee replacement", "total knee arthroplasty", "knee replacement", "tka"),
    "29881": (
        "knee arthroscopy", "knee scope", "meniscectomy", "meniscus surgery",
        "torn meniscus", "arthroscopy with meniscectomy",
    ),
    "43239": (
        "upper gi endoscopy", "upper gi", "endoscopy with biopsy", "egd",
        "stomach scope", "gi biopsy", "endoscopy",
    ),
    "45378": ("colonoscopy", "colon screening", "colon cancer screening", "diagnostic colonoscopy"),
    "70553": (
        "mri brain", "brain mri", "mri with contrast", "brain scan",
        "head mri", "mri of the brain", "mri",
    ),
    "77067": ("mammogram", "mammography", "breast screening", "breast cancer screening"),
    "80053": ("comprehensive metabolic panel", "metabolic panel", "cmp", "chem panel"),
    "82962": ("blood glucose", "glucose test", "blood sugar", "sugar test", "glucose"),
    "83036": ("hemoglobin a1c", "a1c", "hba1c", "diabetes test", "diabetes blood test"),
    "85025": ("complete blood count", "cbc", "blood count"),
    "90837": ("psychotherapy", "therapy session", "talk therapy", "counseling", "counselling"),
    "93000": ("electrocardiogram", "ecg", "ekg", "heart tracing", "heart test"),
    "96127": ("depression screen", "brief depression screening"),
    "99091": (
        "remote patient monitoring", "remote monitoring", "rpm",
        "data analysis", "remote data review",
    ),
    "99213": ("level 3 office visit", "level 3 visit", "follow up visit", "follow-up visit"),
    "99214": ("level 4 office visit", "level 4 visit"),
    "99396": ("preventive visit age 40", "preventive visit 40-64", "adult physical"),
    "99397": (
        "preventive visit age 65", "preventive visit 65+", "senior physical",
        "medicare wellness visit",
    ),
    "99490": ("chronic care management", "chronic care", "care management", "ccm"),
    "G0444": ("annual depression screening", "medicare depression screening"),
}

# Colloquial phrases that genuinely name more than one service.
#
# The load-bearing one is "depression screening": for a DSNP member 96127 is
# COVERED and G0444 is NOT, and the polarity inverts on PPO. Silently picking one
# is a coin flip on telling a member a non-covered service is free. This is a
# correctness path, not a UX nicety.
AMBIGUITY_GROUPS: dict[str, tuple[str, ...]] = {
    "knee": ("27447", "29881"),
    "knee surgery": ("27447", "29881"),
    "knee operation": ("27447", "29881"),
    "depression screening": ("96127", "G0444"),
    "screening for depression": ("96127", "G0444"),
    "depression test": ("96127", "G0444"),
    "blood test": ("80053", "82962", "83036", "85025"),
    "blood work": ("80053", "82962", "83036", "85025"),
    "bloodwork": ("80053", "82962", "83036", "85025"),
    "labs": ("80053", "82962", "83036", "85025"),
    "lab work": ("80053", "82962", "83036", "85025"),
    "office visit": ("99213", "99214"),
    "doctor visit": ("99213", "99214"),
    "preventive visit": ("99396", "99397"),
    "annual visit": ("99396", "99397"),
    "wellness visit": ("99396", "99397"),
    "annual physical": ("99396", "99397"),
    "physical": ("99396", "99397"),
    "checkup": ("99396", "99397"),
    "scope": ("43239", "45378"),
}

# CPT -> ordered specialty preference. An empty tuple means no specialist is the
# right answer (labs/imaging/office visits are ordered by the member's own PCP).
#
# Gastroenterology and Oncology have ZERO in-network providers accepting new
# patients, so 43239/45378 always fall through to the PCP -- which is also the
# clinically correct first step, since a colonoscopy needs a PCP referral anyway.
CPT_SPECIALTY: dict[str, tuple[str, ...]] = {
    "27447": ("Orthopedics",),
    "29881": ("Orthopedics",),
    "43239": ("Gastroenterology",),
    "45378": ("Gastroenterology",),
    "70553": (),  # no Radiology in the directory; the PCP orders imaging
    "77067": ("OB/GYN",),
    "80053": ("Internal Medicine", "Family Medicine"),
    "82962": ("Internal Medicine", "Family Medicine"),
    "83036": ("Endocrinology", "Internal Medicine"),
    "85025": ("Internal Medicine", "Family Medicine"),
    "90837": ("Psychiatry",),
    "93000": ("Cardiology",),
    "96127": ("Psychiatry", "Internal Medicine"),
    "99091": ("Internal Medicine", "Family Medicine"),
    "99213": (),
    "99214": (),
    "99396": ("Internal Medicine", "Family Medicine"),
    "99397": ("Geriatrics", "Internal Medicine"),
    "99490": ("Internal Medicine", "Family Medicine"),
    "G0444": ("Internal Medicine", "Family Medicine"),
}
