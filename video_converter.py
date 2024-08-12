import os
import subprocess
import json

def get_video_bitrate(input_file):
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', input_file]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        bitrate = int(probe_data['format']['bit_rate'])
        return bitrate
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        print(f"Error: Could not determine bitrate for {input_file}. Error: {str(e)}")
        return None

def get_video_duration(file_path):
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        duration = float(probe_data['format']['duration'])
        return duration
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        print(f"Error: Could not determine duration for {file_path}. Error: {str(e)}")
        return None

def check_gpu_availability():
    try:
        result = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True)
        return 'hevc_nvenc' in result.stdout
    except:
        return False
        
def get_video_info(input_file):
    try:
        result = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-show_format', input_file],
                                capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        video_stream = next((stream for stream in probe_data['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            codec = video_stream['codec_name']
            return width, height, codec
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, StopIteration) as e:
        print(f"Error: Could not determine video info for {input_file}. Error: {str(e)}")
    return None, None, None

def convert_video(input_file, output_file, target_resolution=(1920, 1080), use_gpu=True):
    gpu_available = check_gpu_availability() if use_gpu else False

    # Get original bitrate
    original_bitrate = get_video_bitrate(input_file)
    if original_bitrate is None:
        print("Could not determine original bitrate. Using default settings.")
        target_bitrate = "2M"
    else:
        # Set target bitrate slightly lower than original
        target_bitrate = str(int(original_bitrate * 0.9)) # 90% of original bitrate
        
    if gpu_available:
        target_codec = 'hevc_nvenc'
        preset = 'p5'  # High-quality preset for NVENC
        crf = '28'  # Higher CRF for GPU encoding
    else:
        target_codec = 'libx265'
        preset = 'slower'  # Slower preset for better compression
        crf = '23'  # Keep 23 for CPU encoding
    try:
        cmd = [
            'ffmpeg', '-i', input_file,
            '-c:v', target_codec,
            '-crf', crf,
            '-preset', preset,
            '-vf', f'scale={target_resolution[0]}:{target_resolution[1]}',
            '-b:v', target_bitrate,
            '-maxrate', f"{int(int(target_bitrate) * 1.5)}",
            '-bufsize', f"{int(int(target_bitrate) * 2)}",
            '-c:a', 'copy',
            '-c:s', 'copy', # Copy all subtitle streams
            '-map', '0', # Map all streams from the input file
            output_file
        ]
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
        print(f"Conversion completed using {'GPU' if gpu_available else 'CPU'} encoding.")

    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to convert {input_file}. Error: {e.stderr.decode()}")

def process_video(input_file):
    width, height, codec = get_video_info(input_file)
    if width is None or height is None or codec is None:
        print(f"Skipping {input_file} due to info detection failure.")
        return

    needs_conversion = False
    conversion_reason = []

    if width > 1920 or height > 1080:
        needs_conversion = True
        conversion_reason.append("resolution above 1080p")

    if codec.lower() not in ['hevc', 'h265', 'x265']:
        needs_conversion = True
        conversion_reason.append(f"codec is {codec} (not H.265)")

    if needs_conversion:
        print(f"Converting {input_file} to 1080p H.265 because: {', '.join(conversion_reason)}.")
        output_file = os.path.splitext(input_file)[0] + "_1080p_h265" + os.path.splitext(input_file)[1]
        convert_video(input_file, output_file)
        print(f"Conversion complete. Output file: {output_file}")
        
        # Check if the output file exists
        if os.path.exists(output_file):
            # Get durations
            input_duration = get_video_duration(input_file)
            output_duration = get_video_duration(output_file)
            
            if input_duration is not None and output_duration is not None:
                # Compare durations (allow for a small difference due to potential rounding)
                if abs(input_duration - output_duration) < 5:  # Less than 5 second difference
                    try:
                        # os.remove(input_file)
                        print(f"Original file deleted: {input_file}")
                    except OSError as e:
                        print(f"Error: Could not delete original file {input_file}. Error: {str(e)}")
                else:
                    print(f"Warning: Duration mismatch. Input: {input_duration}s, Output: {output_duration}s. Original file not deleted.")
            else:
                print(f"Warning: Could not compare file durations. Original file not deleted.")
        else:
            print(f"Warning: Output file {output_file} does not exist. Original file not deleted.")
    else:
        print(f"{input_file} is already 1080p (or lower) H.265. Skipping...")

def find_video_files(directory):
    supported_formats = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in supported_formats):
                yield os.path.join(root, file)

def main():
    current_directory = os.getcwd()
    print(f"Scanning for video files in {current_directory} and its subdirectories...")
    
    for video_file in find_video_files(current_directory):
        process_video(video_file)

if __name__ == "__main__":
    main()
