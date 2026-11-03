import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
    countCodePoints,
    getFileExtension,
    normalizeTitle,
    validateFile,
    validateTitle,
    validateUpload,
} from "../../static/js/upload-validation.js";

const fixture = JSON.parse(
    fs.readFileSync(
        new URL("../tests_fixtures/upload_validation_cases.json", import.meta.url),
        "utf8",
    ),
);

test("normalizes NFC and trims titles", () => {
    assert.equal(normalizeTitle("  e\u0301e\u0301e\u0301  "), "ééé");
    assert.equal(countCodePoints("😀"), 1);
    assert.equal(countCodePoints("👨‍👩‍👧‍👦"), 7);
});

test("extracts extensions from names with multiple dots", () => {
    assert.equal(getFileExtension("my.video.final.MP4"), "mp4");
    assert.equal(getFileExtension("clip"), "");
});

for (const titleCase of fixture.titleCases) {
    test(`title fixture: ${titleCase.name}`, () => {
        const result = validateTitle(titleCase.input, fixture.config);
        assert.equal(result.valid, titleCase.valid);
        assert.equal(result.normalized, titleCase.normalized);
        assert.equal(result.length, titleCase.length);
        assert.deepEqual(
            result.errors.map((error) => error.code),
            titleCase.codes,
        );
    });
}

for (const fileCase of fixture.fileCases) {
    test(`file fixture: ${fileCase.name}`, () => {
        const result = validateFile(fileCase.file, fixture.config);
        assert.equal(result.valid, fileCase.valid);
        assert.deepEqual(
            result.errors.map((error) => error.code),
            fileCase.codes,
        );
    });
}

test("combined validation requires both title and file", () => {
    const result = validateUpload("", null, fixture.config);
    assert.equal(result.valid, false);
    assert.equal(result.title.errors[0].code, "required");
    assert.equal(result.file.errors[0].code, "required");
});
