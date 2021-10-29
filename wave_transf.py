# We will use wave package available in native Python installation to read and write .wav audio file
import sys
import wave
import matplotlib.pyplot as plt
import numpy as np

def plot_channel_image(data):
    pass



def plot_wave(input_path):

    spf = wave.open(input_path, 'r')
    # Extract Raw Audio from Wav File
    signal = spf.readframes(-1)
    signal = np.fromstring(signal, 'Int16')
    # signal.ravel()
    # Split the data into channels
    channels = [[] for channel in range(spf.getnchannels())]
    for index, datum in enumerate(signal):
        channels[index % len(channels)].append(datum)

    # Get time from indices
    fs = spf.getframerate()
    Time = np.linspace(0, len(signal) / len(channels) / fs, num=len(signal) / len(channels))

    # Plot
    plt.figure(1)
    plt.title('Signal Wave...')
    for channel in channels:
        plt.plot(Time, channel)
    plt.show()

def encode():
    # read wave audio file
    file_path = "/home/moliq/Music/strings0.wav"
    song = wave.open(file_path, mode='rb')
    # Read frames and convert to byte array
    frame_bytes = bytearray(list(song.readframes(song.getnframes())))
    # plot wave
    plot_wave(file_path)
    # The "secret" text message
    string='Peter Parker is the Spiderman!'
    # Append dummy data to fill out rest of the bytes. Receiver shall detect and remove these characters.
    string = string + int((len(frame_bytes)-(len(string)*8*8))/8) *'#'
    # Convert text to bit array
    bits = list(map(int, ''.join([bin(ord(i)).lstrip('0b').rjust(8,'0') for i in string])))

    # Replace LSB of each byte of the audio data by one bit from the text bit array
    for i, bit in enumerate(bits):
        frame_bytes[i] = (frame_bytes[i] & 254) | bit
    # Get the modified bytes
    frame_modified = bytes(frame_bytes)

    # Write bytes to a new wave audio file
    # with wave.open('song_embedded.wav', 'wb') as fd:
    fd = wave.open('/home/moliq/Music/song_embedded.wav', 'wb')
    fd.setparams(song.getparams())
    fd.writeframes(frame_modified)
    fd.close()

def decode():
    # Use wave package (native to Python) for reading the received audio file
    song = wave.open("/home/moliq/Music/song_embedded.wav", mode='rb')
    # Convert audio to byte array
    frame_bytes = bytearray(list(song.readframes(song.getnframes())))

    # Extract the LSB of each byte
    extracted = [frame_bytes[i] & 1 for i in range(len(frame_bytes))]
    # Convert byte array back to string
    string = "".join(chr(int("".join(map(str, extracted[i:i + 8])), 2)) for i in range(0, len(extracted), 8))
    # Cut off at the filler characters
    decoded = string.split("###")[0]

    # Print the extracted text
    print("Sucessfully decoded: " + decoded)
    song.close()


if __name__ == '__main__':
    encode()
    decode()