import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

SAMPLE_RATE = 44100
BPM = 88
BEAT_DUR = 60.0 / BPM
BAR_DUR = BEAT_DUR * 4
TOTAL_DURATION = 60.0  # 60 seconds

def lowpass_filter(data, cutoff, fs=SAMPLE_RATE, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return lfilter(b, a, data)

def highpass_filter(data, cutoff, fs=SAMPLE_RATE, order=2):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    return lfilter(b, a, data)

def synth_rhodes_chord(freqs, duration):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    signal = np.zeros_like(t)
    
    for f in freqs:
        # Fundamental + warm harmonics
        wave = (
            0.6 * np.sin(2 * np.pi * f * t) +
            0.3 * np.sin(2 * np.pi * f * 2 * t) +
            0.15 * np.sin(2 * np.pi * f * 3 * t) +
            0.05 * np.sin(2 * np.pi * f * 4 * t)
        )
        # Soft envelope (quick attack, smooth exponential decay)
        envelope = np.exp(-3.0 * t) * (1 - np.exp(-50.0 * t))
        # Subtle tremolo (vibes)
        tremolo = 1.0 + 0.15 * np.sin(2 * np.pi * 5.0 * t)
        signal += wave * envelope * tremolo
        
    return lowpass_filter(signal, 2200)

def gen_kick(duration=0.3):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    # Pitch drop sweep
    freq = 130.0 * np.exp(-25.0 * t) + 40.0
    envelope = np.exp(-12.0 * t)
    wave = np.sin(2 * np.pi * freq * t) * envelope
    return lowpass_filter(wave, 400)

def gen_snare(duration=0.25):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    # Tone + noise
    tone = np.sin(2 * np.pi * 180.0 * t) * np.exp(-30.0 * t)
    noise = np.random.uniform(-1, 1, len(t)) * np.exp(-15.0 * t)
    noise = highpass_filter(noise, 1000)
    return 0.4 * tone + 0.6 * noise

def gen_hihat(duration=0.1):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    noise = np.random.uniform(-1, 1, len(t)) * np.exp(-40.0 * t)
    return highpass_filter(noise, 4000) * 0.3

def gen_bass(freq, duration):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    wave = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
    envelope = np.exp(-1.5 * t) * (1 - np.exp(-30.0 * t))
    return lowpass_filter(wave * envelope, 350) * 0.7

def create_lofi_track():
    total_samples = int(SAMPLE_RATE * TOTAL_DURATION)
    master_mix = np.zeros(total_samples)
    
    # Chords (Cmaj7 -> Am7 -> Dm7 -> G7) - Upbeat Jazz Lo-Fi Progression
    # Cmaj7: C4, E4, G4, B4 (261.63, 329.63, 392.00, 493.88)
    # Am7:   A3, C4, E4, G4 (220.00, 261.63, 329.63, 392.00)
    # Dm7:   D4, F4, A4, C5 (293.66, 349.23, 440.00, 523.25)
    # G7:    G3, B3, D4, F4 (196.00, 246.94, 293.66, 349.23)
    chords = [
        ([261.63, 329.63, 392.00, 493.88], 130.81), # Cmaj7, Bass C2
        ([220.00, 261.63, 329.63, 392.00], 110.00), # Am7,   Bass A2
        ([293.66, 349.23, 440.00, 523.25], 146.83), # Dm7,   Bass D3
        ([196.00, 246.94, 293.66, 349.23], 98.00),  # G7,    Bass G2
    ]
    
    num_bars = int(np.ceil(TOTAL_DURATION / BAR_DUR))
    
    # Render chords and bass
    for bar in range(num_bars):
        bar_start_sample = int(bar * BAR_DUR * SAMPLE_RATE)
        chord_idx = bar % len(chords)
        chord_freqs, bass_freq = chords[chord_idx]
        
        # Play chord on beat 1 and beat 2.5 (upbeat syncopation)
        r1 = synth_rhodes_chord(chord_freqs, BEAT_DUR * 2)
        b1 = gen_bass(bass_freq, BEAT_DUR * 2)
        
        end1 = min(bar_start_sample + len(r1), total_samples)
        master_mix[bar_start_sample:end1] += r1[:end1-bar_start_sample] * 0.4
        master_mix[bar_start_sample:end1] += b1[:end1-bar_start_sample] * 0.5
        
        # Syncopated chord strike on beat 2.5
        sync_sample = bar_start_sample + int(BEAT_DUR * 1.5 * SAMPLE_RATE)
        r2 = synth_rhodes_chord(chord_freqs, BEAT_DUR * 2.5)
        end2 = min(sync_sample + len(r2), total_samples)
        if sync_sample < total_samples:
            master_mix[sync_sample:end2] += r2[:end2-sync_sample] * 0.35

    # Render Drum Beat Pattern
    kick = gen_kick()
    snare = gen_snare()
    hihat = gen_hihat()
    
    step_dur = BEAT_DUR / 4  # 16th notes
    num_steps = int(TOTAL_DURATION / step_dur)
    
    for step in range(num_steps):
        step_sample = int(step * step_dur * SAMPLE_RATE)
        if step_sample >= total_samples:
            break
            
        step_in_bar = step % 16
        
        # Kick pattern: steps 0, 6, 10
        if step_in_bar in [0, 6, 10]:
            end = min(step_sample + len(kick), total_samples)
            master_mix[step_sample:end] += kick[:end-step_sample] * 0.6
            
        # Snare pattern: steps 4, 12 (beats 2 and 4)
        if step_in_bar in [4, 12]:
            end = min(step_sample + len(snare), total_samples)
            master_mix[step_sample:end] += snare[:end-step_sample] * 0.5
            
        # Hi-hat pattern: every 2 steps (8th notes) with light swing
        if step_in_bar % 2 == 0:
            vol = 0.35 if step_in_bar % 4 == 0 else 0.22
            end = min(step_sample + len(hihat), total_samples)
            master_mix[step_sample:end] += hihat[:end-step_sample] * vol

    # Vinyl crackle / tape noise layer
    crackle = np.random.uniform(-0.02, 0.02, total_samples)
    crackle = lowpass_filter(crackle, 3000)
    master_mix += crackle * 0.15

    # Master lowpass & soft normalization
    master_mix = lowpass_filter(master_mix, 3200)
    max_val = np.max(np.abs(master_mix))
    if max_val > 0:
        master_mix = (master_mix / max_val) * 0.75

    # Save as 16-bit PCM WAV
    audio_int16 = (master_mix * 32767).astype(np.int16)
    wavfile.write("lofi_background.wav", SAMPLE_RATE, audio_int16)
    print("Successfully generated upbeat lo-fi track: lofi_background.wav")

if __name__ == "__main__":
    create_lofi_track()
