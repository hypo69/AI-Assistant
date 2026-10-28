//! Файл: apps/pdf_wasm_converter/rust_engine/src/lib.rs
//! Назначение: Ядро Rust конвертера PDF в структурированный текст и Markdown через WebAssembly.
//! Updated: 2026-10-27 21:17:00

use wasm_bindgen::prelude::*;
use lopdf::Document;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub struct ConversionResult {
    pub total_pages: usize,
    pub plain_text: String,
    pub markdown: String,
}

/// Инициализация паники с выводом в консоль браузера
#[wasm_bindgen(start)]
pub fn init_console() {
    // Режим отладки для WebAssembly
}

/// Конвертирует массив байтов PDF в Markdown и чистый текст
#[wasm_bindgen]
pub fn convert_pdf_bytes(pdf_bytes: &[u8]) -> Result<JsValue, JsValue> {
    // 1. Загрузка документа из среза памяти
    let doc = Document::load_mem(pdf_bytes)
        .map_err(|e| JsValue::from_str(&format!("Ошибка разбора PDF: {:?}", e)))?;

    let pages = doc.get_pages();
    let total_pages = pages.len();
    let mut full_text = String::new();
    let mut full_md = String::new();

    // 2. Итерация по страницам и извлечение текстовых блоков
    for (page_num, &page_id) in pages.iter() {
        full_md.push_str(&format!("### Страница {}\n\n", page_num));
        full_text.push_str(&format!("--- Страница {} ---\n", page_num));

        if let Ok(text) = doc.extract_text(&[page_num]) {
            for line in text.lines() {
                let trimmed = line.trim();
                if !trimmed.is_empty() {
                    full_text.push_str(trimmed);
                    full_text.push('\n');

                    // Эвристика: если строка короткая и без точки в конце — оформляем как заголовок
                    if trimmed.len() < 50 && !trimmed.ends_with('.') && !trimmed.ends_with(',') {
                        full_md.push_str(&format!("## {}\n\n", trimmed));
                    } else {
                        full_md.push_str(&format!("{}\n\n", trimmed));
                    }
                }
            }
        }
    }

    let result = ConversionResult {
        total_pages,
        plain_text: full_text,
        markdown: full_md,
    };

    serde_wasm_bindgen::to_value(&result)
        .map_err(|e| JsValue::from_str(&format!("Ошибка сериализации JSON: {:?}", e)))
}
