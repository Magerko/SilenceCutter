"""Дочерний процесс распознавания речи.

Запускается отдельно от интерфейса намеренно: Qt6 и ctranslate2 конфликтуют
при загрузке нативных библиотек, и если Qt загружается первым, распознавание
падает с нарушением доступа. Отдельный процесс не наследует загруженные Qt
библиотеки, поэтому конфликта нет.

Побочная выгода: аварийное падение нативного кода больше не уносит интерфейс,
а отмена сводится к снятию процесса.

ВАЖНО: здесь нельзя импортировать PyQt6 - ни прямо, ни через utils.
Обмен идёт текстом: прогресс в stderr, результат в stdout в формате JSON.
"""
import argparse
import json
import os
import sys


def _emit(kind: str, *values) -> None:
    """Служебная строка для родителя. Идёт в stderr, чтобы не мешать JSON."""
    print(kind + ' ' + ' '.join(str(v) for v in values), file=sys.stderr, flush=True)


def _model_dir(models_root: str, model_size: str) -> str:
    return os.path.join(models_root, model_size)


def _is_ready(folder: str) -> bool:
    if not os.path.isdir(folder):
        return False
    names = set(os.listdir(folder))
    return 'model.bin' in names and 'tokenizer.json' in names


def _folder_size_mb(path: str) -> float:
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total / (1024 * 1024)


def _download(folder: str, model_size: str, expected_mb: float) -> None:
    import threading

    from faster_whisper import download_model

    os.makedirs(folder, exist_ok=True)
    failure = []

    def worker():
        try:
            download_model(model_size, output_dir=folder)
        except BaseException as exc:  # noqa: BLE001 - передаём в основной поток
            failure.append(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    _emit('DOWNLOAD_START', model_size, f'{expected_mb:.0f}')

    while thread.is_alive():
        thread.join(timeout=0.5)
        done = _folder_size_mb(folder)
        percent = min(99, int(done / expected_mb * 100)) if expected_mb else 0
        _emit('DOWNLOAD', percent, f'{done:.1f}', f'{expected_mb:.0f}')

    if failure:
        raise failure[0]
    _emit('DOWNLOAD', 100, f'{_folder_size_mb(folder):.1f}', f'{expected_mb:.0f}')


def run(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--transcribe-worker', action='store_true')
    parser.add_argument('--audio', required=True)
    parser.add_argument('--models-root', required=True)
    parser.add_argument('--model', default='large-v3')
    parser.add_argument('--language', default='')
    parser.add_argument('--expected-mb', type=float, default=0.0)
    args = parser.parse_args(argv)

    folder = _model_dir(args.models_root, args.model)
    if not _is_ready(folder):
        _download(folder, args.model, args.expected_mb)

    def attempt(device: str, compute_type: str):
        """Полный проход распознавания на заданном устройстве.

        Сегменты вычисляются лениво, поэтому нехватка библиотек CUDA всплывает
        не при создании модели, а на первом кадре. Значит, проверять
        работоспособность видеокарты можно только фактическим проходом.
        """
        from faster_whisper import WhisperModel

        model = WhisperModel(folder, device=device, compute_type=compute_type)
        segments, info = model.transcribe(
            args.audio,
            language=args.language or None,
            word_timestamps=True,
            beam_size=5,
            # VAD выбрасывает короткие вставки между словами - ровно то, что ищем.
            vad_filter=False,
            # Без опоры на предыдущий текст меньше домыслов и больше пойманных
            # коротких слов.
            condition_on_previous_text=False,
        )
        total = getattr(info, 'duration', 0.0) or 0.0
        collected = []
        for segment in segments:
            for word in (getattr(segment, 'words', None) or []):
                collected.append({'text': word.word,
                                  'start': word.start, 'end': word.end})
            if total > 0:
                _emit('PROGRESS', min(99, int(segment.end / total * 100)))
        return collected, total

    # Видеокарта заметно быстрее, но требует установленных библиотек CUDA.
    # Пробуем её и честно откатываемся, если они отсутствуют.
    candidates = [('cpu', 'int8')]
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            candidates.insert(0, ('cuda', 'float16'))
    except Exception:
        pass

    words, duration, device = None, 0.0, 'cpu'
    for index, (candidate_device, compute_type) in enumerate(candidates):
        try:
            words, duration = attempt(candidate_device, compute_type)
            device = candidate_device
            break
        except Exception as exc:
            last = index == len(candidates) - 1
            if last:
                raise
            _emit('FALLBACK', candidate_device, str(exc).replace('\n', ' ')[:120])

    _emit('DEVICE', device)
    _emit('PROGRESS', 100)
    json.dump({'words': words, 'duration': duration, 'device': device},
              sys.stdout, ensure_ascii=False)
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(run())
