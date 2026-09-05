import streamlit as st
import re

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from PIL import Image
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
    page_title="BMI Calculator",
    page_icon="⚖️",
    layout="centered"
)


# ============================================================
# SESSION STATE INITIALIZATION
# IMPORTANT:
# This MUST happen before widgets are created.
# ============================================================

DEFAULTS = {
    "weight_value": 60.0,
    "weight_unit_value": "Kilograms (kg)",

    "height_cm_value": 165.0,
    "height_unit_value": "Centimeters (cm)",

    "feet_value": 5,
    "inches_value": 5.0,

    "extracted_weight": None,
    "extracted_height": None,
    "extracted_text": "",

    "file_processed": False,
    "bmi_result": None,

    "uploaded_file_name": "",

    # Counter used to reset the Streamlit file uploader
    "clear_uploader": 0
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# TITLE
# ============================================================

st.markdown(
    '<div class="main-title">⚖️ BMI Calculator</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Calculate your Body Mass Index easily</div>',
    unsafe_allow_html=True
)


# ============================================================
# FUNCTIONS
# ============================================================

def pounds_to_kg(pounds):
    """Convert pounds to kilograms."""
    return pounds * 0.45359237


def calculate_bmi(weight, weight_unit, height_cm):
    """Calculate BMI."""

    if weight <= 0:
        return None

    if height_cm <= 0:
        return None

    # Convert weight to kg
    if weight_unit == "Pounds (lb)":
        weight_kg = pounds_to_kg(weight)
    else:
        weight_kg = weight

    # Convert height to meters
    height_m = height_cm / 100

    if height_m <= 0:
        return None

    bmi = weight_kg / (height_m ** 2)

    return bmi


def get_bmi_category(bmi):
    """Return BMI category."""

    if bmi < 18.5:
        return "Underweight"

    elif bmi < 25:
        return "Normal weight"

    elif bmi < 30:
        return "Overweight"

    else:
        return "Obesity"


def extract_pdf_text(uploaded_file):
    """Extract text from a normal PDF."""

    if not PDF_AVAILABLE:
        return ""

    try:
        file_bytes = uploaded_file.read()

        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        text = ""

        for page in document:
            text += page.get_text()

        document.close()

        return text

    except Exception:
        return ""


def extract_image_text(uploaded_file):
    """Extract text from an image using OCR."""

    if not PIL_AVAILABLE or not OCR_AVAILABLE:
        return ""

    try:
        image = Image.open(uploaded_file)

        text = pytesseract.image_to_string(image)

        return text

    except Exception:
        return ""


def extract_scanned_pdf_text(uploaded_file):
    """OCR scanned PDF pages."""

    if not PDF_AVAILABLE or not PIL_AVAILABLE or not OCR_AVAILABLE:
        return ""

    try:
        file_bytes = uploaded_file.read()

        document = fitz.open(
            stream=file_bytes,
            filetype="pdf"
        )

        text = ""

        for page in document:

            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2)
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            page_text = pytesseract.image_to_string(image)

            text += page_text + "\n"

        document.close()

        return text

    except Exception:
        return ""


def process_file(uploaded_file):
    """Process PDF or image."""

    if uploaded_file is None:
        return ""

    filename = uploaded_file.name.lower()

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if filename.endswith(".pdf"):

        text = extract_pdf_text(uploaded_file)

        # If normal PDF text extraction fails,
        # try OCR.
        if not text.strip():

            uploaded_file.seek(0)

            text = extract_scanned_pdf_text(
                uploaded_file
            )

        return text

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    elif filename.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
    ):

        return extract_image_text(uploaded_file)

    return ""


def extract_weight(text):
    """
    Extract weight from text.

    Examples:
    87.1 kg
    Weight: 87.1 kg
    87 kg
    190 lb
    """

    if not text:
        return None

    # Weight with kg
    patterns_kg = [
        r"(?:weight|wt)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*kg\b",
        r"(\d+(?:\.\d+)?)\s*kg\b"
    ]

    for pattern in patterns_kg:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            try:
                return float(match.group(1))
            except:
                pass

    # Weight with pounds
    patterns_lb = [
        r"(?:weight|wt)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)\b",
        r"(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)\b"
    ]

    for pattern in patterns_lb:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            try:
                pounds = float(match.group(1))

                return pounds_to_kg(pounds)

            except:
                pass

    return None


def extract_height(text):
    """
    Extract height.

    Supported examples:

    161 cm
    Height: 161 cm
    1.61 m
    5'4"
    5 ft 4 in
    """

    if not text:
        return None

    # --------------------------------------------------------
    # Centimeters
    # --------------------------------------------------------

    patterns_cm = [
        r"(?:height|ht)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*cm\b",
        r"(\d+(?:\.\d+)?)\s*cm\b"
    ]

    for pattern in patterns_cm:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            try:
                height_cm = float(match.group(1))

                if 50 <= height_cm <= 250:
                    return height_cm / 100

            except:
                pass

    # --------------------------------------------------------
    # Meters
    # --------------------------------------------------------

    patterns_m = [
        r"(?:height|ht)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*m\b",
        r"(\d+(?:\.\d+)?)\s*m\b"
    ]

    for pattern in patterns_m:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            try:
                height_m = float(match.group(1))

                if 0.5 <= height_m <= 2.5:
                    return height_m

            except:
                pass

    # --------------------------------------------------------
    # Feet and inches
    # Example: 5'4"
    # --------------------------------------------------------

    pattern_feet_inches = (
        r"(\d+)\s*['’]\s*"
        r"(\d+(?:\.\d+)?)\s*"
        r"(?:[\"”]|in|inch|inches)?"
    )

    match = re.search(
        pattern_feet_inches,
        text,
        flags=re.IGNORECASE
    )

    if match:

        try:

            feet = float(match.group(1))
            inches = float(match.group(2))

            total_inches = (
                feet * 12 + inches
            )

            height_cm = total_inches * 2.54

            if 50 <= height_cm <= 250:
                return height_cm / 100

        except:
            pass

    # --------------------------------------------------------
    # Feet and inches written as text
    # Example: 5 ft 4 in
    # --------------------------------------------------------

    pattern_text = (
        r"(\d+)\s*(?:ft|feet)\s*"
        r"(\d+(?:\.\d+)?)?\s*"
        r"(?:in|inch|inches)?"
    )

    match = re.search(
        pattern_text,
        text,
        flags=re.IGNORECASE
    )

    if match:

        try:

            feet = float(match.group(1))

            inches = (
                float(match.group(2))
                if match.group(2)
                else 0
            )

            total_inches = (
                feet * 12 + inches
            )

            height_cm = total_inches * 2.54

            if 50 <= height_cm <= 250:
                return height_cm / 100

        except:
            pass

    return None


# ============================================================
# RESET CALLBACK
# ============================================================

def reset_form():
    """
    Reset all widget values.

    IMPORTANT:
    This function is called by the Reset button callback.
    """

    st.session_state.weight_value = 60.0

    st.session_state.weight_unit_value = (
        "Kilograms (kg)"
    )

    st.session_state.height_cm_value = 165.0

    st.session_state.height_unit_value = (
        "Centimeters (cm)"
    )

    st.session_state.feet_value = 5

    st.session_state.inches_value = 5.0

    st.session_state.extracted_weight = None

    st.session_state.extracted_height = None

    st.session_state.extracted_text = ""

    st.session_state.file_processed = False

    st.session_state.bmi_result = None

    st.session_state.uploaded_file_name = ""


# ============================================================
# CLEAR UPLOADED FILE CALLBACK
# ============================================================

def clear_upload():
    """
    Clear the uploaded file and all extracted information.

    The BMI calculator's manual values and BMI result are left unchanged.
    The uploader key is changed so Streamlit creates a fresh uploader.
    """

    st.session_state.extracted_weight = None
    st.session_state.extracted_height = None
    st.session_state.extracted_text = ""
    st.session_state.file_processed = False
    st.session_state.uploaded_file_name = ""

    # Force Streamlit to create a fresh file uploader
    st.session_state.clear_uploader += 1


# ============================================================
# FILL FORM CALLBACK
# ============================================================

def fill_form_from_extracted():
    """
    Fill the BMI form using extracted values.

    This is a callback, so it can safely update
    widget session-state values.
    """

    # --------------------------------------------------------
    # Weight
    # --------------------------------------------------------

    if st.session_state.extracted_weight is not None:

        st.session_state.weight_value = round(
            st.session_state.extracted_weight,
            1
        )

        st.session_state.weight_unit_value = (
            "Kilograms (kg)"
        )

    # --------------------------------------------------------
    # Height
    # --------------------------------------------------------

    if st.session_state.extracted_height is not None:

        height_cm = (
            st.session_state.extracted_height * 100
        )

        st.session_state.height_cm_value = round(
            height_cm,
            1
        )

        st.session_state.height_unit_value = (
            "Centimeters (cm)"
        )

    # Clear old result
    st.session_state.bmi_result = None


# ============================================================
# MANUAL BMI CALCULATOR
# ============================================================

st.header("🧮 BMI Calculator")

st.write(
    "Enter your weight and height below."
)


# ============================================================
# WEIGHT
# ============================================================

st.subheader("⚖️ Weight")

st.selectbox(
    "Weight Unit",
    [
        "Kilograms (kg)",
        "Pounds (lb)"
    ],
    key="weight_unit_value"
)

st.number_input(
    "Weight",
    min_value=1.0,
    max_value=500.0,
    step=0.1,
    key="weight_value"
)


# ============================================================
# HEIGHT
# ============================================================

st.subheader("📏 Height")

st.selectbox(
    "Height Unit",
    [
        "Centimeters (cm)",
        "Feet / Inches"
    ],
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

    current_height_cm = (
        st.session_state.height_cm_value
    )

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


# ============================================================
# BUTTONS
# ============================================================

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


# ============================================================
# CALCULATE BMI
# ============================================================

if calculate_clicked:

    current_weight = (
        st.session_state.weight_value
    )

    current_weight_unit = (
        st.session_state.weight_unit_value
    )

    bmi = calculate_bmi(
        current_weight,
        current_weight_unit,
        current_height_cm
    )

    if bmi is None:

        st.error(
            "Please enter valid weight and height."
        )

    else:

        st.session_state.bmi_result = bmi


# ============================================================
# SHOW BMI RESULT
# ============================================================

if st.session_state.bmi_result is not None:

    bmi = st.session_state.bmi_result

    category = get_bmi_category(bmi)

    st.metric("BMI Result", f"{bmi:.1f}")
    st.info(f"Category: {category}")


# ============================================================
# BMI REFERENCE
# ============================================================

st.subheader("📊 BMI Reference")

st.markdown(
    """
    | BMI | Category |
    |---|---|
    | Below 18.5 | Underweight |
    | 18.5 – 24.9 | Normal weight |
    | 25.0 – 29.9 | Overweight |
    | 30.0 and above | Obesity |
    """
)


# ============================================================
# UPLOAD SECTION
# ============================================================

st.divider()

st.header("📄 Upload Document or Image")

st.write(
    "Upload a PDF or image containing weight and height."
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

# Clear uploaded file and extracted text
if uploaded_file is not None:
    st.button(
        "🗑️ Clear Uploaded File & Extracted Text",
        use_container_width=True,
        on_click=clear_upload
    )


# ============================================================
# PROCESS UPLOADED FILE
# ============================================================

if uploaded_file is not None:

    # Only process a new file
    if (
        st.session_state.uploaded_file_name
        != uploaded_file.name
    ):

        st.session_state.uploaded_file_name = (
            uploaded_file.name
        )

        st.session_state.extracted_weight = None
        st.session_state.extracted_height = None
        st.session_state.extracted_text = ""

        uploaded_file.seek(0)

        with st.spinner(
            "🔍 Reading the uploaded file..."
        ):

            extracted_text = process_file(
                uploaded_file
            )

        st.session_state.extracted_text = (
            extracted_text
        )

        st.session_state.extracted_weight = (
            extract_weight(extracted_text)
        )

        st.session_state.extracted_height = (
            extract_height(extracted_text)
        )

        st.session_state.file_processed = True


# ============================================================
# DISPLAY EXTRACTION RESULTS
# ============================================================

if st.session_state.file_processed:

    st.subheader("🔎 Extracted Information")

    extracted_weight = (
        st.session_state.extracted_weight
    )

    extracted_height = (
        st.session_state.extracted_height
    )

    # --------------------------------------------------------
    # Weight result
    # --------------------------------------------------------

    if extracted_weight is not None:

        st.success(
            f"⚖️ Weight found: "
            f"{extracted_weight:.1f} kg"
        )

    else:

        st.warning(
            "⚠️ Weight could not be detected."
        )

    # --------------------------------------------------------
    # Height result
    # --------------------------------------------------------

    if extracted_height is not None:

        height_cm = (
            extracted_height * 100
        )

        st.success(
            f"📏 Height found: "
            f"{height_cm:.1f} cm"
        )

    else:

        st.warning(
            "⚠️ Height could not be detected."
        )


# ============================================================
# FILL FORM FROM EXTRACTED VALUES
# ============================================================

if (
    st.session_state.extracted_weight is not None
    and
    st.session_state.extracted_height is not None
):

    st.success(
        "✅ Both weight and height were detected."
    )

    st.write(
        "Click the button below to automatically "
        "fill the BMI calculator."
    )

    st.button(
        "📥 Fill BMI Form Automatically",
        use_container_width=True,
        type="primary",
        on_click=fill_form_from_extracted
    )

elif st.session_state.file_processed:

    st.warning(
        "⚠️ Both weight and height could not "
        "be detected automatically."
    )

    st.write(
        "Please enter the missing information manually."
    )


# ============================================================
# SHOW EXTRACTED TEXT
# ============================================================

if st.session_state.extracted_text:

    with st.expander(
        "📃 Show extracted text"
    ):

        st.text(
            st.session_state.extracted_text
        )

        if st.button(
            "🧹 Clear Extracted Text",
            use_container_width=True
        ):
            st.session_state.extracted_text = ""
            st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption("BMI Calculator | Python + Streamlit")
st.caption("Najma Hassan | U-Learns")
