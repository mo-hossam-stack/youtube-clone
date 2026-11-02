import { validateUpload } from "./upload-validation.js";

const $ = (id) => document.getElementById(id);

const form = $("uploadForm");
const configNode = $("upload-config");
if (!form || !configNode) {
    throw new Error("Upload form is not available");
}

const config = JSON.parse(configNode.textContent);
const titleInput = $("id_title");
const titleCounter = $("titleCounter");
const titleError = $("titleError");
const fileInput = $("id_video_file");
const fileError = $("videoFileError");
const fileLabel = $("video-label");
const errorContainer = $("errorContainer");
const submitBtn = $("submitBtn");
const overlay = $("uploadOverlay");
const uploadStatus = $("uploadStatus");
const thumbInput = $("customThumbnail");
const thumbPreview = $("thumbPreview");
const thumbLabel = $("thumb-label");
const thumbnailData = $("thumbnailData");

const touched = { title: false, file: false };
let submitting = false;

function renderField(input, output, errors, show) {
    const first = show && errors.length ? errors[0] : null;
    output.textContent = first ? first.message : "";
    input.classList.toggle("invalid", Boolean(first));
    input.setAttribute("aria-invalid", first ? "true" : "false");
}

function update() {
    const result = validateUpload(
        titleInput.value,
        fileInput.files[0] || null,
        config,
    );
    titleCounter.textContent = `${result.title.length}/${config.title.max}`;
    titleCounter.classList.toggle(
        "invalid",
        touched.title && !result.title.valid,
    );
    renderField(titleInput, titleError, result.title.errors, touched.title);
    renderField(fileInput, fileError, result.file.errors, touched.file);

    submitBtn.disabled = submitting || !result.valid;
    return result;
}

function clearGlobalErrors() {
    errorContainer.replaceChildren();
}

function addGlobalError(message) {
    let list = errorContainer.querySelector(".error-list");
    if (!list) {
        list = document.createElement("ul");
        list.className = "error-list";
        errorContainer.replaceChildren(list);
    }
    const item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
}

function showServerErrors(payload) {
    clearGlobalErrors();
    let errors = payload && payload.errors ? payload.errors : null;
    if (Array.isArray(errors)) {
        errors = {
            __all__: errors.map((message) => ({ message: String(message) })),
        };
    }
    if (!errors) {
        addGlobalError("Upload failed. Please try again.");
        return;
    }

    let firstInvalid = null;
    for (const [field, rawItems] of Object.entries(errors)) {
        const items = Array.isArray(rawItems) ? rawItems : [rawItems];
        const messages = items
            .map((item) => (
                typeof item === "string" ? item : item && item.message
            ))
            .filter(Boolean);

        if (field === "title" || field === "video_file") {
            const input = field === "title" ? titleInput : fileInput;
            const output = field === "title" ? titleError : fileError;
            output.textContent = messages.join(" ");
            input.classList.add("invalid");
            input.setAttribute("aria-invalid", "true");
            if (!firstInvalid) {
                firstInvalid = input;
            }
        } else {
            messages.forEach(addGlobalError);
        }
    }

    if (firstInvalid) {
        firstInvalid.focus();
    }
}

async function parseResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
        try {
            return await response.json();
        } catch {
            return null;
        }
    }
    return null;
}

async function submitUpload(event) {
    event.preventDefault();
    touched.title = true;
    touched.file = true;
    const result = update();

    if (!result.valid || submitting) {
        const target = !result.title.valid ? titleInput : fileInput;
        target.focus();
        return;
    }

    submitting = true;
    update();
    clearGlobalErrors();
    overlay.classList.add("active");
    window.onbeforeunload = () => "Upload in progress";

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
        });
        const payload = await parseResponse(response);

        if (response.ok && payload && payload.success) {
            window.onbeforeunload = null;
            uploadStatus.textContent = "Upload complete!";
            setTimeout(() => {
                window.location.href = form.dataset.redirectUrl;
            }, 500);
            return;
        }

        submitting = false;
        overlay.classList.remove("active");
        update();
        showServerErrors(payload);
    } catch {
        submitting = false;
        overlay.classList.remove("active");
        window.onbeforeunload = null;
        update();
        clearGlobalErrors();
        addGlobalError("Upload failed. Please try again.");
    }
}

titleInput.addEventListener("input", () => {
    touched.title = true;
    update();
});
titleInput.addEventListener("blur", () => {
    touched.title = true;
    update();
});

fileInput.addEventListener("change", () => {
    touched.file = true;
    const file = fileInput.files[0];
    fileLabel.textContent = file ? file.name : "Click to select a video file";
    update();
});

thumbInput.addEventListener("change", () => {
    const file = thumbInput.files[0];
    if (!file) {
        return;
    }
    const reader = new FileReader();
    reader.onload = (readerEvent) => {
        thumbPreview.src = readerEvent.target.result;
        thumbPreview.classList.add("visible");
        thumbLabel.style.display = "none";
        thumbnailData.value = readerEvent.target.result;
    };
    reader.readAsDataURL(file);
});

form.noValidate = true;
form.addEventListener("submit", submitUpload);
update();
