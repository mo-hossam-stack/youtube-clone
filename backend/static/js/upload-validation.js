export function normalizeTitle(value) {
    return String(value || "").normalize("NFC").trim();
}

export function countCodePoints(value) {
    return Array.from(value).length;
}

export function getFileExtension(name) {
    const base = String(name || "").split(/[\\/]/).pop();
    const dot = base.lastIndexOf(".");
    return dot > 0 ? base.slice(dot + 1).toLowerCase() : "";
}

function makeError(code, message) {
    return { code, message };
}

export function validateTitle(value, config) {
    const normalized = normalizeTitle(value);
    const length = countCodePoints(normalized);
    const messages = config.messages.title;

    if (!normalized) {
        return {
            valid: false,
            normalized,
            length,
            errors: [makeError("required", messages.required)],
        };
    }
    if (length < config.title.min) {
        return {
            valid: false,
            normalized,
            length,
            errors: [makeError("min_length", messages.min_length)],
        };
    }
    if (length > config.title.max) {
        return {
            valid: false,
            normalized,
            length,
            errors: [makeError(
                "max_length",
                messages.max_length.replace("{length}", String(length)),
            )],
        };
    }
    if (normalized.includes("<") || normalized.includes(">")) {
        return {
            valid: false,
            normalized,
            length,
            errors: [makeError(
                "invalid_characters",
                messages.invalid_characters,
            )],
        };
    }
    if (/\p{Cc}/u.test(normalized)) {
        return {
            valid: false,
            normalized,
            length,
            errors: [makeError(
                "control_characters",
                messages.control_characters,
            )],
        };
    }

    return { valid: true, normalized, length, errors: [] };
}

export function validateFile(file, config) {
    const messages = config.messages.file;

    if (!file) {
        return {
            valid: false,
            errors: [makeError("required", messages.required)],
        };
    }
    if (file.size === 0) {
        return {
            valid: false,
            errors: [makeError("empty_file", messages.empty_file)],
        };
    }
    if (file.size > config.file.maxBytes) {
        return {
            valid: false,
            errors: [makeError("file_too_large", messages.file_too_large)],
        };
    }

    const extension = getFileExtension(file.name);
    const allowed = config.file.allowedExtensions.map(
        (item) => item.toLowerCase(),
    );
    if (!allowed.includes(extension)) {
        return {
            valid: false,
            errors: [makeError("invalid_extension", messages.invalid_extension)],
        };
    }

    return { valid: true, errors: [] };
}

export function validateUpload(title, file, config) {
    const titleResult = validateTitle(title, config);
    const fileResult = validateFile(file, config);
    return {
        valid: titleResult.valid && fileResult.valid,
        title: titleResult,
        file: fileResult,
    };
}
