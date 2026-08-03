import os
import os.path
import pathlib
import shutil
from typing import Dict, List
import traceback

from billiard.context import Process
from billiard.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .celery import app
from .models import (DynamicMix, SourceFile, StaticMix, TaskStatus,
                     YTAudioDownloadTask)
from .separators.registry import build_separator, get_separator_spec
from .util import output_format_to_ext, get_valid_filename
from .youtubedl import download_audio, get_file_ext

"""
This module defines various Celery tasks used for Spleeter Web.
"""

def get_separator(separator: str, separator_args: Dict, bitrate: int,
                  cpu_separation: bool):
    """Returns separator object for corresponding source separation model."""
    return build_separator(separator, separator_args, bitrate, cpu_separation,
                           settings)

@app.task()
def create_static_mix(static_mix_id):
    """
    Task to create static mix and write to appropriate storage backend.
    :param static_mix_id: The id of the StaticMix to be processed
    """
    # Mark as in progress
    try:
        static_mix = StaticMix.objects.get(id=static_mix_id)
    except StaticMix.DoesNotExist:
        # Does not exist, perhaps due to stale task
        print('StaticMix does not exist')
        return
    static_mix.status = TaskStatus.IN_PROGRESS
    static_mix.save()

    ext = output_format_to_ext(static_mix.bitrate)

    try:
        # Get paths
        directory = os.path.join(settings.MEDIA_ROOT, settings.SEPARATE_DIR,
                                 static_mix_id)
        filename = get_valid_filename(static_mix.formatted_name()) + f'.{ext}'
        rel_media_path = os.path.join(settings.SEPARATE_DIR, static_mix_id,
                                      filename)
        rel_path = os.path.join(settings.MEDIA_ROOT, rel_media_path)
        rel_path_dir = os.path.join(settings.MEDIA_ROOT, settings.SEPARATE_DIR,
                                    static_mix_id)

        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
        try:
            separator = get_separator(static_mix.separator,
                                      static_mix.separator_args,
                                      static_mix.bitrate,
                                      settings.CPU_SEPARATION)
        except ValueError as exc:
            static_mix.status = TaskStatus.ERROR
            static_mix.error = str(exc)
            static_mix.date_finished = timezone.now()
            static_mix.save()
            return

        spec = get_separator_spec(static_mix.separator)
        parts = {part: getattr(static_mix, part) for part in spec.stems}

        # Non-local filesystems like S3/Azure Blob do not support source_path()
        is_local = settings.DEFAULT_FILE_STORAGE == 'api.storage.FileSystemStorage'
        path = static_mix.source_path() if is_local else static_mix.source_url(
        )

        if not settings.CPU_SEPARATION:
            # For GPU separation, do separation in separate process.
            # Otherwise, GPU memory is not automatically freed afterwards
            process_eval = Process(target=separator.create_static_mix,
                                   args=(parts, path, rel_path))
            process_eval.start()
            try:
                process_eval.join()
            except SoftTimeLimitExceeded as e:
                # Kill process if user aborts task
                process_eval.terminate()
                raise e
        else:
            separator.create_static_mix(parts, path, rel_path)

        # Check file exists
        if os.path.exists(rel_path):
            static_mix.status = TaskStatus.DONE
            static_mix.date_finished = timezone.now()
            if is_local:
                # File is already on local filesystem
                static_mix.file.name = rel_media_path
            else:
                # Need to copy local file to S3/Azure Blob/etc.
                raw_file = open(rel_path, 'rb')
                content_file = ContentFile(raw_file.read())
                content_file.name = filename
                static_mix.file = content_file
                # Remove local file
                os.remove(rel_path)
                # Remove empty directory
                os.rmdir(rel_path_dir)
            static_mix.save()
        else:
            raise Exception('Error writing to file')
    except FileNotFoundError as error:
        print(error)
        print('Please make sure you have FFmpeg and FFprobe installed.')
        static_mix.status = TaskStatus.ERROR
        static_mix.date_finished = timezone.now()
        static_mix.error = str(error)
        static_mix.save()
    except SoftTimeLimitExceeded:
        print('Aborted!')
    except Exception as error:
        print(traceback.format_exc())
        static_mix.status = TaskStatus.ERROR
        static_mix.date_finished = timezone.now()
        static_mix.error = str(error)
        static_mix.save()

@app.task()
def create_dynamic_mix(dynamic_mix_id):
    """
    Task to create dynamic mix and write to appropriate storage backend.
    :param dynamic_mix_id: The id of the audio track model (StaticMix) to be processed
    """
    # Mark as in progress
    try:
        dynamic_mix = DynamicMix.objects.get(id=dynamic_mix_id)
    except DynamicMix.DoesNotExist:
        # Does not exist, perhaps due to stale task
        print('DynamicMix does not exist')
        return
    dynamic_mix.status = TaskStatus.IN_PROGRESS
    dynamic_mix.save()

    try:
        # Get paths
        directory = os.path.join(settings.MEDIA_ROOT, settings.SEPARATE_DIR,
                                 dynamic_mix_id)
        rel_media_path = os.path.join(settings.SEPARATE_DIR, dynamic_mix_id)
        file_prefix = get_valid_filename(dynamic_mix.formatted_prefix())
        file_suffix = dynamic_mix.formatted_suffix()
        rel_path = os.path.join(settings.MEDIA_ROOT, rel_media_path)

        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
        try:
            separator = get_separator(dynamic_mix.separator,
                                      dynamic_mix.separator_args,
                                      dynamic_mix.bitrate,
                                      settings.CPU_SEPARATION)
        except ValueError as exc:
            dynamic_mix.status = TaskStatus.ERROR
            dynamic_mix.error = str(exc)
            dynamic_mix.date_finished = timezone.now()
            dynamic_mix.save()
            return

        all_parts = get_separator_spec(dynamic_mix.separator).stems

        # Non-local filesystems like S3/Azure Blob do not support source_path()
        is_local = settings.DEFAULT_FILE_STORAGE == 'api.storage.FileSystemStorage'
        path = dynamic_mix.source_path(
        ) if is_local else dynamic_mix.source_url()

        # Do separation
        if not settings.CPU_SEPARATION:
            # For GPU separation, do separation in separate process.
            # Otherwise, GPU memory is not automatically freed afterwards
            process_eval = Process(target=separator.separate_into_parts,
                                   args=(path, rel_path))
            process_eval.start()
            try:
                process_eval.join()
            except SoftTimeLimitExceeded as e:
                # Kill process if user aborts task
                process_eval.terminate()
                raise e
        else:
            separator.separate_into_parts(path, rel_path)

        ext = output_format_to_ext(dynamic_mix.bitrate)
        # Check all parts exist
        if exists_all_parts(rel_path, ext, all_parts):
            rename_all_parts(rel_path, file_prefix, file_suffix, ext,
                             all_parts)
            dynamic_mix.status = TaskStatus.DONE
            dynamic_mix.date_finished = timezone.now()
            if is_local:
                save_to_local_storage(dynamic_mix, rel_media_path, file_prefix,
                                      file_suffix, ext, all_parts)
            else:
                save_to_ext_storage(dynamic_mix, rel_path, file_prefix,
                                    file_suffix, ext, all_parts)
        else:
            raise Exception('Error writing to file')
    except FileNotFoundError as error:
        print(traceback.format_exc())
        print('Please make sure you have FFmpeg and FFprobe installed.')
        dynamic_mix.status = TaskStatus.ERROR
        dynamic_mix.date_finished = timezone.now()
        dynamic_mix.error = str(error)
        dynamic_mix.save()
    except SoftTimeLimitExceeded:
        print('Aborted!')
    except Exception as error:
        print(traceback.format_exc())
        dynamic_mix.status = TaskStatus.ERROR
        dynamic_mix.date_finished = timezone.now()
        dynamic_mix.error = str(error)
        dynamic_mix.save()

@app.task(autoretry_for=(Exception, ),
          default_retry_delay=3,
          retry_kwargs={'max_retries': settings.YOUTUBE_MAX_RETRIES})
def fetch_youtube_audio(source_file_id, fetch_task_id, artist, title, link):
    """
    Task that uses youtubedl to extract the audio from a YouTube link.

    :param source_file_id: SourceFile id
    :param fetch_task_id: YouTube audio fetch task model id
    :param artist: Track artist
    :param title: Track title
    :param link: YouTube link
    """
    try:
        source_file = SourceFile.objects.get(id=source_file_id)
    except SourceFile.DoesNotExist:
        # Does not exist, perhaps due to stale task
        print('SourceFile does not exist')
        return
    fetch_task = YTAudioDownloadTask.objects.get(id=fetch_task_id)
    # Mark as in progress
    fetch_task.status = TaskStatus.IN_PROGRESS
    fetch_task.save()

    try:
        # Get paths
        directory = os.path.join(settings.MEDIA_ROOT, settings.UPLOAD_DIR,
                                 str(source_file_id))
        filename = get_valid_filename(artist + ' - ' +
                                      title) + get_file_ext(link)
        rel_media_path = os.path.join(settings.UPLOAD_DIR, str(source_file_id),
                                      filename)
        rel_path = os.path.join(settings.MEDIA_ROOT, rel_media_path)
        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)

        # Start download
        download_audio(link, rel_path)

        is_local = settings.DEFAULT_FILE_STORAGE == 'api.storage.FileSystemStorage'

        # Check file exists
        if os.path.exists(rel_path):
            fetch_task.status = TaskStatus.DONE
            fetch_task.date_finished = timezone.now()
            if is_local:
                # File is already on local filesystem
                source_file.file.name = rel_media_path
            else:
                # Need to copy local file to S3/Azure Blob/etc.
                raw_file = open(rel_path, 'rb')
                content_file = ContentFile(raw_file.read())
                content_file.name = filename
                source_file.file = content_file
                rel_dir_path = os.path.join(settings.MEDIA_ROOT,
                                            settings.UPLOAD_DIR,
                                            source_file_id)
                # Remove local file
                os.remove(rel_path)
                # Remove empty directory
                os.rmdir(rel_dir_path)
            fetch_task.save()
            source_file.save()
        else:
            raise Exception('Error writing to file')
    except SoftTimeLimitExceeded:
        print('Aborted!')
    except Exception as error:
        print(traceback.format_exc())
        fetch_task.status = TaskStatus.ERROR
        fetch_task.date_finished = timezone.now()
        fetch_task.error = str(error)
        fetch_task.save()
        raise error

def exists_all_parts(rel_path, ext, parts: List[str]):
    """Returns whether all of the individual component tracks exist on filesystem."""
    for part in parts:
        rel_part_path = os.path.join(rel_path, f'{part}.{ext}')
        if not os.path.exists(rel_part_path):
            print(f'{rel_part_path} does not exist')
            return False
    return True

def rename_all_parts(rel_path, file_prefix: str, file_suffix: str, ext: str, parts: List[str]):
    """Renames individual part files to names with track artist and title."""
    for part in parts:
        old_rel_path = os.path.join(rel_path, f'{part}.{ext}')
        new_rel_path = os.path.join(
            rel_path, f'{file_prefix} ({part}) {file_suffix}.{ext}')
        print(f'Renaming {old_rel_path} to {new_rel_path}')
        os.rename(old_rel_path, new_rel_path)

# Maps stem names produced by separators to DynamicMix FileField attributes.
_PART_FILE_FIELDS = {
    'vocals': 'vocals_file',
    'other': 'other_file',
    'bass': 'bass_file',
    'drums': 'drums_file',
    'piano': 'piano_file',
    'guitar': 'guitar_file',
}


def save_to_local_storage(dynamic_mix,
                          rel_media_path,
                          file_prefix: str,
                          file_suffix: str,
                          ext: str,
                          parts: List[str]):
    """Saves individual parts to the local file system

    :param dynamic_mix: DynamicMix model
    :param rel_media_path: Relative path from media/ to DynamicMix ID directory
    :param file_prefix: Filename prefix
    :param parts: Stem names that were actually produced for this mix
    """
    # Only bind FileFields for stems that exist. Assigning bass/drums for
    # 2-stem models (e.g. Mel-RoFormer) leaves phantom URLs that break Mixer.
    for part in parts:
        field_name = _PART_FILE_FIELDS[part]
        rel_part_path = os.path.join(
            rel_media_path, f'{file_prefix} ({part}) {file_suffix}.{ext}')
        getattr(dynamic_mix, field_name).name = rel_part_path

    dynamic_mix.save()

def save_to_ext_storage(dynamic_mix, rel_path_dir, file_prefix: str,
                        file_suffix: str, ext: str, parts: List[str]):
    """Saves individual parts to external file storage (S3, Azure, etc.)

    :param dynamic_mix: DynamicMix model
    :param rel_path_dir: Relative path to DynamicMix ID directory
    :param file_prefix: Filename prefix
    :param parts: Stem names that were actually produced for this mix
    """
    for part in parts:
        field_name = _PART_FILE_FIELDS[part]
        filename = f'{file_prefix} ({part}) {file_suffix}.{ext}'
        rel_path = os.path.join(rel_path_dir, filename)
        with open(rel_path, 'rb') as raw_file:
            content_file = ContentFile(raw_file.read())
        content_file.name = filename
        setattr(dynamic_mix, field_name, content_file)

    dynamic_mix.save()

    shutil.rmtree(rel_path_dir, ignore_errors=True)
