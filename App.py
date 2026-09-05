
import streamlit as st
import re
import io

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="BMI Calculator - OCR",
    page_icon="⚖️",
    layout="centered"
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "weight_value": 60.0,
    "weight_unit_value": "Kilograms (kg)",
    "height_cm_value": 165.0,
    "height_unit_value": "Centimeters (cm)",
    "feet_value": 5,
    "inches_value": 5.0,

    "extracted_weight": None,
    "extracted_height": None,  # stored in meters
    "extracted_text": "",
    "file_processed": False,
    "bmi_result": None,
    "uploaded_file_name": "",
    "clear_uploader": 0,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
.main-title {
    font-size: 2.2rem;
    font-weight: 700;
    text-align: center;
}
.subtitle {
    text-align: center;
    color: #666;
    margin-bottom: 1.5rem;
}
.detected-box {
    padding: 12px;
    border-radius: 10px;
    border: 1px solid #ddd;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


st.markdown(
    '<div class="main-title">⚖️ BMI Calculator</div>',
    unsafe_allow_html=True
)
st.markdown(
    '<div class="subtitle">Calculate BMI manually or extract weight and height from a report/photo</div>',
    unsafe_allow_html=True
)


# ============================================================
# BMI FUNCTIONS
# ============================================================

def pounds_to_kg(pounds):
    return pounds * 0.45359237


def calculate_bmi(weight, weight_unit, height_cm):
    if weight <= 0 or height_cm <= 0:
        return None

    if weight_unit == "Pounds (lb)":
        weight_kg = pounds_to_kg(weight)
    else:
        weight_kg = weight

    height_m = height_cm / 100.0

    if height_m <= 0:
        return None

    return weight_kg / (height_m ** 2)


def get_bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal weight"
    elif bmi < 30:
        return "Overweight"
    return "Obesity"


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def preprocess_image(image):
    """
    Prepare a photo/report for OCR.
    Multiple versions are generated because receipts and
    printed reports can have different contrast/lighting.
    """
    if not PIL_AVAILABLE:
        return []

    image = image.convert("RGB")

    # Correct EXIF orientation if possible
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    # Make the image larger for OCR
    width, height = image.size
    scale = 2.5

    if width < 1800:
        scale = max(scale, 1800 / width)

    if scale > 4:
        scale = 4

    image = image.resize(
        (int(width * scale), int(height * scale)),
        Image.Resampling.LANCZOS
    )

    gray = ImageOps.grayscale(image)

    # Improve contrast and sharpness
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    gray = ImageEnhance.Sharpness(gray).enhance(2.0)

    # Lightly sharpen
    gray = gray.filter(ImageFilter.SHARPEN)

    # Normal grayscale version
    versions = [gray]

    # Auto-contrast version
    auto = ImageOps.autocontrast(gray)
    versions.append(auto)

    # Threshold version
    threshold = auto.point(lambda p: 255 if p > 165 else 0)
    versions.append(threshold)

    return versions


# ============================================================
# OCR
# ============================================================

def ocr_image(uploaded_file):
    """
    OCR an image using several preprocessing versions and
    several Tesseract page segmentation modes.
    """
    if not PIL_AVAILABLE or not OCR_AVAILABLE:
        return ""

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        versions = preprocess_image(image)

        all_text = []

        configs = [
            "--psm 6",
            "--psm 11",
            "--psm 12",
        ]

        for processed in versions:
            for config in configs:
                try:
                    text = pytesseract.image_to_string(
                        processed,
                        config=config
                    )
                    if text and text.strip():
                        all_text.append(text)
                except Exception:
                    pass

        # Keep all OCR text. Extraction functions use the combined
        # text and prioritize labelled values.
        return "\n".join(all_text)

    except Exception:
        return ""


def extract_pdf_text(uploaded_file):
    """Extract text from a normal/text PDF."""
    if not PDF_AVAILABLE:
        return ""

    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()

        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        text = ""

        for page in document:
            text += page.get_text() + "\n"

        document.close()
        return text

    except Exception:
        return ""


def extract_scanned_pdf_text(uploaded_file):
    """OCR scanned PDF pages."""
    if not PDF_AVAILABLE or not PIL_AVAILABLE or not OCR_AVAILABLE:
        return ""

    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()

        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        text_parts = []

        for page in document:
            pix = page.get_pixmap(
                matrix=fitz.Matrix(2.5, 2.5),
                alpha=False
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            versions = preprocess_image(image)

            for processed in versions:
                for config in ["--psm 6", "--psm 11"]:
                    try:
                        page_text = pytesseract.image_to_string(
                            processed,
                            config=config
                        )
                        if page_text.strip():
                            text_parts.append(page_text)
                    except Exception:
                        pass

        document.close()

        return "\n".join(text_parts)

    except Exception:
        return ""


def process_file(uploaded_file):
    """Process PDF or image."""
    if uploaded_file is None:
        return ""

    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        text = extract_pdf_text(uploaded_file)

        # If normal extraction gives little/no text, use OCR.
        if len(text.strip()) < 20:
            uploaded_file.seek(0)
            text = extract_scanned_pdf_text(uploaded_file)

        return text

    if filename.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
    ):
        return ocr_image(uploaded_file)

    return ""


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_ocr_text(text):
    """
    Normalize common OCR errors without destroying useful
    information.
    """
    if not text:
        return ""

    text = text.replace("：", ":")
    text = text.replace("，", ".")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("’", "'")
    text = text.replace("”", '"')
    text = text.replace("\r", "\n")

    # OCR sometimes separates decimal point from number.
    text = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", text)

    # Normalize repeated whitespace, but keep line structure.
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def number_value(value):
    """Convert OCR number such as 87,1 or 87.1 to float."""
    if value is None:
        return None

    value = value.replace(",", ".")

    try:
        return float(value)
    except Exception:
        return None


# ============================================================
# WEIGHT EXTRACTION
# ============================================================

def extract_weight(text):
    """
    Detect body weight in kg/lb.

    The function prioritizes values near a Weight/Wt label so
    reports containing many other kg values are less likely to
    produce a false result.
    """
    if not text:
        return None

    text = normalize_ocr_text(text)

    # OCR can produce small spelling variations:
    # Weight, Weighl, Weiqht, Wt, Weit, etc.
    weight_label = r"(?:weight|weigh[tli]|wei[gq]ht|wt)\b"

    # Strong pattern:
    # Weight: 87.1 kg
    # Weight (kg): 88.3
    labelled_patterns = [
        rf"{weight_label}\s*(?:\([^)]+\))?\s*[:=\-]?\s*"
        r"(\d{2,3}(?:[.,]\d+)?)\s*(kg|kgs|kilograms?|lb|lbs|pounds?)?\b",

        rf"{weight_label}\s*(?:\([^)]+\))?\s*"
        r"(\d{2,3}(?:[.,]\d+)?)\s*(kg|kgs|kilograms?|lb|lbs|pounds?)\b",
    ]

    for pattern in labelled_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = number_value(match.group(1))
            unit = (match.group(2) or "kg").lower()

            if value is not None and 20 <= value <= 500:
                if unit.startswith(("lb", "pound")):
                    return pounds_to_kg(value)
                return value

    # Look line-by-line. This works particularly well for:
    # "Weight (kg) 88.3"
    # "Weight : 87.1 kg"
    for line in text.splitlines():
        low = line.lower()

        if re.search(weight_label, low):
            matches = re.findall(
                r"(\d{2,3}(?:[.,]\d+)?)\s*(kg|kgs|kilograms?|lb|lbs|pounds?)?",
                line,
                flags=re.IGNORECASE
            )

            for raw_value, raw_unit in matches:
                value = number_value(raw_value)
                unit = (raw_unit or "kg").lower()

                if value is None:
                    continue

                if 20 <= value <= 500:
                    if raw_unit and unit.startswith(("lb", "pound")):
                        return pounds_to_kg(value)

                    # In a line explicitly labelled Weight, an
                    # unqualified 2-digit/3-digit value is assumed kg.
                    return value

    # More flexible fallback for OCR where the label and value
    # are separated by a line break.
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if re.search(weight_label, line, flags=re.IGNORECASE):
            nearby = "\n".join(lines[i:i + 3])

            match = re.search(
                r"(\d{2,3}(?:[.,]\d+)?)\s*(kg|kgs|kilograms?|lb|lbs|pounds?)?",
                nearby,
                flags=re.IGNORECASE
            )

            if match:
                value = number_value(match.group(1))
                unit = (match.group(2) or "kg").lower()

                if value is not None and 20 <= value <= 500:
                    if unit.startswith(("lb", "pound")):
                        return pounds_to_kg(value)
                    return value

    return None


# ============================================================
# HEIGHT EXTRACTION
# ============================================================

def extract_height(text):
    """
    Detect height in cm, meters, or feet/inches.

    Returns height in meters.
    """
    if not text:
        return None

    text = normalize_ocr_text(text)

    height_label = r"(?:height|heig[hli]t|heigth|heigt|ht)\b"

    # --------------------------------------------------------
    # 1. Height label + centimeters
    # --------------------------------------------------------

    patterns_cm = [
        rf"{height_label}\s*(?:\([^)]+\))?\s*[:=\-]?\s*"
        r"(\d{2,3}(?:[.,]\d+)?)\s*cm\b",

        rf"{height_label}\s*(?:\([^)]+\))?\s*"
        r"(\d{2,3}(?:[.,]\d+)?)\s*cm\b",
    ]

    for pattern in patterns_cm:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            value = number_value(match.group(1))

            if value is not None and 50 <= value <= 250:
                return value / 100.0

    # --------------------------------------------------------
    # 2. Any valid cm value near Height
    # --------------------------------------------------------

    for line in text.splitlines():
        if re.search(height_label, line, flags=re.IGNORECASE):
            match = re.search(
                r"(\d{2,3}(?:[.,]\d+)?)\s*cm\b",
                line,
                flags=re.IGNORECASE
            )

            if match:
                value = number_value(match.group(1))

                if value is not None and 50 <= value <= 250:
                    return value / 100.0

    # --------------------------------------------------------
    # 3. Height in meters
    # --------------------------------------------------------

    patterns_m = [
        rf"{height_label}\s*(?:\([^)]+\))?\s*[:=\-]?\s*"
        r"(1(?:[.,]\d+)?)\s*m\b",

        rf"{height_label}\s*(?:\([^)]+\))?\s*"
        r"(1(?:[.,]\d+)?)\s*m\b",
    ]

    for pattern in patterns_m:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            value = number_value(match.group(1))

            if value is not None and 0.5 <= value <= 2.5:
                return value

    # --------------------------------------------------------
    # 4. Feet and inches: 5'4", 5' 4", 5 ft 4 in
    # --------------------------------------------------------

    pattern_feet_inches = (
        r"(\d)\s*['’]\s*"
        r"(\d{1,2}(?:[.,]\d+)?)\s*"
        r"(?:[\"”]|in|inch|inches)?"
    )

    match = re.search(
        pattern_feet_inches,
        text,
        flags=re.IGNORECASE
    )

    if match:
        feet = number_value(match.group(1))
        inches = number_value(match.group(2))

        if feet is not None and inches is not None:
            if 1 <= feet <= 8 and 0 <= inches < 12:
                total_inches = feet * 12 + inches
                height_cm = total_inches * 2.54

                if 50 <= height_cm <= 250:
                    return height_cm / 100.0

    pattern_text = (
        r"(\d)\s*(?:ft|feet)\s*"
        r"(\d{1,2}(?:[.,]\d+)?)?\s*"
        r"(?:in|inch|inches)?"
    )

    match = re.search(
        pattern_text,
        text,
        flags=re.IGNORECASE
    )

    if match:
        feet = number_value(match.group(1))
        inches = (
            number_value(match.group(2))
            if match.group(2)
            else 0
        )

        if feet is not None and inches is not None:
            if 1 <= feet <= 8 and 0 <= inches < 12:
                total_inches = feet * 12 + inches
                height_cm = total_inches * 2.54

                if 50 <= height_cm <= 250:
                    return height_cm / 100.0

    # --------------------------------------------------------
    # 5. Label and value separated by a line break
    # --------------------------------------------------------

    lines = text.splitlines()

    for i, line in enumerate(lines):
        if re.search(height_label, line, flags=re.IGNORECASE):
            nearby = "\n".join(lines[i:i + 3])

            # cm
            match = re.search(
                r"(\d{2,3}(?:[.,]\d+)?)\s*cm\b",
                nearby,
                flags=re.IGNORECASE
            )

            if match:
                value = number_value(match.group(1))

                if value is not None and 50 <= value <= 250:
                    return value / 100.0

            # meters
            match = re.search(
                r"(1(?:[.,]\d+)?)\s*m\b",
                nearby,
                flags=re.IGNORECASE
            )

            if match:
                value = number_value(match.group(1))

                if value is not None and 0.5 <= value <= 2.5:
                    return value

    return None


# ============================================================
# RESET / CLEAR / FILL
# ============================================================

def reset_form():
    st.session_state.weight_value = 60.0
    st.session_state.weight_unit_value = "Kilograms (kg)"
    st.session_state.height_cm_value = 165.0
    st.session_state.height_unit_value = "Centimeters (cm)"
    st.session_state.feet_value = 5
    st.session_state.inches_value = 5.0

    st.session_state.extracted_weight = None
    st.session_state.extracted_height = None
    st.session_state.extracted_text = ""
    st.session_state.file_processed = False
    st.session_state.bmi_result = None
    st.session_state.uploaded_file_name = ""


def clear_upload():
    st.session_state.extracted_weight = None
    st.session_state.extracted_height = None
    st.session_state.extracted_text = ""
    st.session_state.file_processed = False
    st.session_state.uploaded_file_name = ""
    st.session_state.clear_uploader += 1


def fill_form_from_extracted():
    if st.session_state.extracted_weight is not None:
        st.session_state.weight_value = round(
            st.session_state.extracted_weight, 1
        )
        st.session_state.weight_unit_value = "Kilograms (kg)"

    if st.session_state.extracted_height is not None:
        height_cm = st.session_state.extracted_height * 100

        st.session_state.height_cm_value = round(
            height_cm, 1
        )
        st.session_state.height_unit_value = "Centimeters (cm)"

    st.session_state.bmi_result = None


# ============================================================
# MANUAL BMI CALCULATOR
# ============================================================

st.header("🧮 BMI Calculator")
st.write("Enter your weight and height below, or extract them from a report.")

st.subheader("⚖️ Weight")

st.selectbox(
    "Weight Unit",
    ["Kilograms (kg)", "Pounds (lb)"],
    key="weight_unit_value"
)

st.number_input(
    "Weight",
    min_value=1.0,
    max_value=500.0,
    step=0.1,
    key="weight_value"
)

st.subheader("📏 Height")

st.selectbox(
    "Height Unit",
    ["Centimeters (cm)", "Feet / Inches"],
    key="height_unit_value"
)

if st.session_state.height_unit_value == "Centimeters (cm)":

    st.number_input(
        "Height (cm)",
        min_value=50.0,
        max_value=250.0,
        step=0.1,
        key="height_cm_value"
    )

    current_height_cm = st.session_state.height_cm_value

else:

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Feet",
            min_value=1,
            max_value=8,
            step=1,
            key="feet_value"
        )

    with col2:
        st.number_input(
            "Inches",
            min_value=0.0,
            max_value=11.9,
            step=0.1,
            key="inches_value"
        )

    current_height_cm = (
        st.session_state.feet_value * 30.48
        + st.session_state.inches_value * 2.54
    )


col1, col2 = st.columns(2)

with col1:
    calculate_clicked = st.button(
        "🧮 Calculate BMI",
        use_container_width=True,
        type="primary"
    )

with col2:
    st.button(
        "🔄 Reset",
        use_container_width=True,
        on_click=reset_form
    )


if calculate_clicked:

    bmi = calculate_bmi(
        st.session_state.weight_value,
        st.session_state.weight_unit_value,
        current_height_cm
    )

    if bmi is None:
        st.error("Please enter valid weight and height.")
    else:
        st.session_state.bmi_result = bmi


if st.session_state.bmi_result is not None:

    bmi = st.session_state.bmi_result
    category = get_bmi_category(bmi)

    st.metric("BMI Result", f"{bmi:.1f}")
    st.info(f"Category: {category}")


st.subheader("📊 BMI Reference")

st.markdown("""
| BMI | Category |
|---|---|
| Below 18.5 | Underweight |
| 18.5 – 24.9 | Normal weight |
| 25.0 – 29.9 | Overweight |
| 30.0 and above | Obesity |
""")


# ============================================================
# UPLOAD SECTION
# ============================================================

st.divider()

st.header("📄 Upload Document or Image")

st.write(
    "Upload a body-composition report, receipt, photo, or PDF. "
    "The app will try to detect Height and Weight automatically."
)

if not PDF_AVAILABLE or not OCR_AVAILABLE:
    st.warning(
        "OCR/PDF libraries are not installed. "
        "In Google Colab, run: pip install streamlit pymupdf pillow pytesseract"
    )

uploaded_file = st.file_uploader(
    "Choose a file",
    type=[
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "bmp",
        "tiff"
    ],
    key=f"file_uploader_{st.session_state.clear_uploader}"
)

if uploaded_file is not None:

    st.button(
        "🗑️ Clear Uploaded File & Extracted Text",
        use_container_width=True,
        on_click=clear_upload
    )

    if (
        st.session_state.uploaded_file_name
        != uploaded_file.name
    ):

        st.session_state.uploaded_file_name = uploaded_file.name
        st.session_state.extracted_weight = None
        st.session_state.extracted_height = None
        st.session_state.extracted_text = ""

        uploaded_file.seek(0)

        with st.spinner("🔍 Reading and analyzing the uploaded file..."):
            extracted_text = process_file(uploaded_file)

        st.session_state.extracted_text = extracted_text

        st.session_state.extracted_weight = extract_weight(
            extracted_text
        )

        st.session_state.extracted_height = extract_height(
            extracted_text
        )

        st.session_state.file_processed = True


# ============================================================
# EXTRACTION RESULTS
# ============================================================

if st.session_state.file_processed:

    st.subheader("🔎 Extracted Information")

    extracted_weight = st.session_state.extracted_weight
    extracted_height = st.session_state.extracted_height

    col1, col2 = st.columns(2)

    with col1:
        if extracted_weight is not None:
            st.success(
                f"⚖️ Weight found\n\n"
                f"**{extracted_weight:.1f} kg**"
            )
        else:
            st.warning("⚠️ Weight could not be detected.")

    with col2:
        if extracted_height is not None:
            height_cm = extracted_height * 100

            st.success(
                f"📏 Height found\n\n"
                f"**{height_cm:.1f} cm**"
            )
        else:
            st.warning("⚠️ Height could not be detected.")

    if (
        extracted_weight is not None
        and extracted_height is not None
    ):

        st.success(
            "✅ Both weight and height were detected successfully."
        )

        st.button(
            "📥 Fill BMI Form Automatically",
            use_container_width=True,
            type="primary",
            on_click=fill_form_from_extracted
        )

        # Show the BMI based directly on extracted values
        extracted_bmi = calculate_bmi(
            extracted_weight,
            "Kilograms (kg)",
            extracted_height * 100
        )

        if extracted_bmi is not None:
            st.info(
                f"📊 BMI from extracted values: "
                f"**{extracted_bmi:.1f}** — "
                f"{get_bmi_category(extracted_bmi)}"
            )

    else:

        st.warning(
            "⚠️ One or both measurements could not be detected automatically."
        )

        st.write(
            "Please enter the missing information manually."
        )


# ============================================================
# OCR TEXT
# ============================================================

if st.session_state.extracted_text:

    with st.expander("📃 Show OCR / Extracted Text"):

        st.text(
            st.session_state.extracted_text
        )

        st.caption(
            "If a value is not detected, inspect this text. "
            "It shows what the OCR engine actually read."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption("BMI Calculator | Python + Streamlit + OCR")
st.caption("Najma Hassan | U-Learns")
