import os
from io import BytesIO
import numpy as np
import soundfile as sf
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pydub import AudioSegment
from threading import Thread
import pyloudnorm as pyln

VALID_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.aac', '.ogg', '.m4a'}

def calculate_loudness(audio_segment):
    sample_rate = audio_segment.frame_rate
    audio_bytes = audio_segment.export(format="wav").read()
    with BytesIO(audio_bytes) as audio_file:
        data, _sample_rate = sf.read(audio_file)
    assert sample_rate == _sample_rate
    meter = pyln.Meter(sample_rate)
    loudness = meter.integrated_loudness(data)
    return loudness

def adjust_gain(audio_segment, gain_dB):
    return audio_segment.apply_gain(gain_dB)

def adjust_stems_in_folder(stems_folder, target_loudness_LUFS, output_base_folder):
    stems = []
    filenames = []
    for filename in os.listdir(stems_folder):
        if any(filename.lower().endswith(ext) for ext in VALID_AUDIO_EXTENSIONS):
            filepath = os.path.join(stems_folder, filename)
            audio = AudioSegment.from_file(filepath)
            stems.append(audio)
            filenames.append(filename)

    if not stems:
        print(f"No audio files found in {stems_folder}")
        return

    main_mix = AudioSegment.silent(duration=stems[0].duration_seconds * 1000)
    for i, stem in enumerate(stems):
        main_mix = main_mix.overlay(stem)
    combined_loudness_LUFS = calculate_loudness(main_mix)
    print(f"Detected audio loudness: {combined_loudness_LUFS:.2f} LUFS")
    gain_adjustment_dB = target_loudness_LUFS - combined_loudness_LUFS
    print(f"Gain to apply to every stem: {gain_adjustment_dB:.2f} db")
    adjusted_stems = [adjust_gain(stem, gain_adjustment_dB) for stem in stems]

    song_name = os.path.basename(stems_folder)
    output_folder_name = f"{song_name}_{target_loudness_LUFS}LUFS"
    output_folder = os.path.join(output_base_folder, output_folder_name)
    os.makedirs(output_folder, exist_ok=True)

    for filename, adjusted_stem in zip(filenames, adjusted_stems):
        output_path = os.path.join(output_folder, filename)
        adjusted_stem.export(output_path, format='wav')

    print(f"Adjusted stems saved to {output_folder}")
    
def verify_output_loudness(output_folder, target_loudness_LUFS):
    stems = []
    for filename in os.listdir(output_folder):
        if any(filename.lower().endswith(ext) for ext in VALID_AUDIO_EXTENSIONS):
            filepath = os.path.join(output_folder, filename)
            audio = AudioSegment.from_file(filepath)
            stems.append(audio)
    if not stems:
        print(f"No audio files found in {stems_folder}")
        return
    main_mix = AudioSegment.silent(duration=stems[0].duration_seconds * 1000)
    for i, stem in enumerate(stems):
        main_mix = main_mix.overlay(stem)
    combined_loudness_LUFS = calculate_loudness(main_mix)
    print(f"Combined loudness of output stems: {combined_loudness_LUFS:.2f} LUFS")
    return np.isclose(combined_loudness_LUFS, target_loudness_LUFS, atol=0.1)

def process_folders(input_folder, output_folder, target_loudness_LUFS, button, progress):
    button.config(state=tk.DISABLED)
    try:
        subfolders = [os.path.join(input_folder, subfolder) for subfolder in os.listdir(input_folder) if os.path.isdir(os.path.join(input_folder, subfolder))]
        total_subfolders = len(subfolders)
        progress["maximum"] = total_subfolders
        for i, subfolder_path in enumerate(subfolders, 1):
            print(f"Processing folder: {subfolder_path}")
            adjust_stems_in_folder(subfolder_path, target_loudness_LUFS, output_folder)
            output_folder_name = f"{os.path.basename(subfolder_path)}_{target_loudness_LUFS}LUFS"
            output_subfolder = os.path.join(output_folder, output_folder_name)
            if verify_output_loudness(output_subfolder, target_loudness_LUFS):
                print(f"Loudness verification passed for {output_subfolder}")
            else:
                print(f"Loudness verification failed for {output_subfolder}")
            progress["value"] = i
            progress.update_idletasks()
        messagebox.showinfo("Success", "All stems have been processed successfully.")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        button.config(state=tk.NORMAL)
        progress["value"] = 0

def start_processing(input_folder, output_folder, target_loudness_LUFS, button, progress):
    thread = Thread(target=process_folders, args=(input_folder, output_folder, target_loudness_LUFS, button, progress))
    thread.start()

def select_input_folder(entry):
    folder = filedialog.askdirectory()
    entry.delete(0, tk.END)
    entry.insert(0, folder)

def select_output_folder(entry):
    folder = filedialog.askdirectory()
    entry.delete(0, tk.END)
    entry.insert(0, folder)

def main():
    root = tk.Tk()
    root.title("Audio Stem Normalizer")

    tk.Label(root, text="Input Folder:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
    input_folder_entry = tk.Entry(root, width=50)
    input_folder_entry.grid(row=0, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse...", command=lambda: select_input_folder(input_folder_entry)).grid(row=0, column=2, padx=10, pady=10)

    tk.Label(root, text="Output Folder:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
    output_folder_entry = tk.Entry(root, width=50)
    output_folder_entry.grid(row=1, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse...", command=lambda: select_output_folder(output_folder_entry)).grid(row=1, column=2, padx=10, pady=10)

    tk.Label(root, text="Target Loudness (LUFS):").grid(row=2, column=0, padx=10, pady=10, sticky="e")
    loudness_entry = tk.Entry(root, width=10)
    loudness_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")
    loudness_entry.insert(0, "-14.0")

    process_button = tk.Button(root, text="Normalize", command=lambda: start_processing(input_folder_entry.get(), output_folder_entry.get(), float(loudness_entry.get()), process_button, progress))
    process_button.grid(row=3, columnspan=3, pady=20)

    progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
    progress.grid(row=4, columnspan=3, pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
