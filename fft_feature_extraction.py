import numpy as np
import scipy.io.wavfile as wav
import matplotlib.pyplot as plt

# 这是特征提取函数（AI编写的核心逻辑）
def extract_features(audio_file):
    print(f"正在分析文件: {audio_file}")
    
    # 1. 读取音频数据 (由于你是mp4，实际用需转为wav，这里为演示框架)
    # sample_rate, data = wav.read(audio_file) 
    
    # 为了演示，我们生成一个模拟的数据，代表你提取的真实音频
    sample_rate = 44100 # 采样率
    t = np.linspace(0, 10, 10 * sample_rate)
    # 模拟正常高档风扇的“嗡嗡声”（低频为主，混合一点高频）
    data = 0.5 * np.sin(2 * np.pi * 100 * t) + 0.2 * np.sin(2 * np.pi * 300 * t)
    
    # 时域特征：计算均方根(RMS)，代表声音的能量大小
    rms = np.sqrt(np.mean(data**2))
    print(f"时域特征 - 声音能量(RMS): {rms:.4f}")
    
    # 频域特征：进行 FFT 变换
    fft_data = np.abs(np.fft.rfft(data))
    freqs = np.fft.rfftfreq(len(data), 1/sample_rate)
    
    # 找出最大的频率峰值（主频）
    peak_freq = freqs[np.argmax(fft_data)]
    print(f"频域特征 - 主频峰值: {peak_freq} Hz")
    
    # 绘制频谱图 (频谱图是AI分类的重要依据)
    plt.figure(figsize=(10, 4))
    plt.plot(freqs, fft_data, color='blue')
    plt.title(f"FFT Spectrum - {audio_file}")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Amplitude")
    plt.xlim(0, 2000) # 风扇声音主要在低频段，我们只看前2000Hz
    plt.savefig('spectrum_plot.png') # 保存图片
    print("已生成频谱图: spectrum_plot.png")

# 运行测试
extract_features("模拟风扇音频.mp4")