# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Tts Module
# =============================================================================
# Description:
#   Модуль синтеза и распознавания речи (TTS / STT) с ленивой загрузкой зависимостей.
#   Загрузка внешних пакетов (speech_recognition, pydub, gTTS) выполняется
#   непосредственно при вызове функций, не блокируя импорт пакета utils.
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.tts import speech_recognizer, text2speech
#
#     res = speech_recognizer(audio_file_path=Path("audio.wav"))
#     path = await text2speech("Привет мир", lang="ru")
#
# File: tts.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:45:00
# =============================================================================

"""Синтез и распознавание речи с ленивой загрузкой зависимостей."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
from typing import Optional
import requests

from logger import logger


def speech_recognizer(
    audio_url: Optional[str] = None,
    audio_file_path: Optional[Path] = None,
    language: str = "ru-RU",
) -> str:
    """Загрузка аудиофайла и распознавание речи в нём.

    Args:
        audio_url: URL аудиофайла для загрузки.
        audio_file_path: Локальный путь к аудиофайлу.
        language: Код языка распознавания (по умолчанию 'ru-RU').

    Returns:
        str: Распознанный текст или сообщение об ошибке.
    """
    try:
        import speech_recognition as sr
        from pydub import AudioSegment
    except ImportError as exc:
        logger.warning(f"Для распознавания речи требуются пакеты speech_recognition и pydub: {exc}")
        return "Модули распознавания речи не установлены."

    try:
        if audio_url:
            response = requests.get(audio_url, timeout=30)
            audio_file_path = Path(tempfile.gettempdir()) / "recognized_audio.ogg"
            with open(audio_file_path, "wb") as f:
                f.write(response.content)

        if not audio_file_path:
            return "Не указан аудиофайл для распознавания."

        wav_file_path = audio_file_path.with_suffix(".wav")
        audio = AudioSegment.from_file(audio_file_path)
        audio.export(wav_file_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(str(wav_file_path)) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data, language=language)
                logger.info(f"Распознанный текст: {text}")
                return text
            except sr.UnknownValueError:
                logger.error("Google Speech Recognition не смог распознать аудио")
                return "Не удалось распознать речь в аудиофайле."
            except sr.RequestError as exc:
                logger.error(f"Ошибка запроса к сервису Google Speech Recognition: {exc}")
                return "Ошибка сервиса распознавания речи."
    except Exception as exc:
        logger.error(f"Ошибка в speech_recognizer: {exc}")
        return "Ошибка в процессе распознавания речи."


async def text2speech(text: str, lang: str = "ru") -> str:
    """Преобразование текста в речь и сохранение в аудиофайл.

    Args:
        text: Текст для озвучивания.
        lang: Код языка озвучивания (по умолчанию 'ru').

    Returns:
        str: Путь к сгенерированному аудиофайлу.
    """
    try:
        from gtts import gTTS
    except ImportError as exc:
        logger.warning(f"Для синтеза речи требуется пакет gTTS: {exc}")
        return ""

    try:
        tts = gTTS(text=text, lang=lang)
        audio_file_path = str(Path(tempfile.gettempdir()) / "response.mp3")
        tts.save(audio_file_path)

        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_file_path, format="mp3")
            wav_file_path = str(Path(audio_file_path).with_suffix(".wav"))
            audio.export(wav_file_path, format="wav")
            logger.info(f"TTS аудиофайл сохранен: {wav_file_path}")
            return wav_file_path
        except Exception as pydub_exc:
            logger.warning(f"Конвертация через pydub пропущена (возможно, ffmpeg не установлен): {pydub_exc}")
            logger.warning(f"TTS аудиофайл сохранен как MP3: {audio_file_path}")
            return audio_file_path
    except Exception as exc:
        logger.error(f"Ошибка в text2speech: {exc}")
        return ""
