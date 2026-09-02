// 浏览器端：把录音 blob（webm/opus）解码并编码为 WAV（16bit PCM 单声道）
export async function blobToWav(blob) {
  const arrayBuffer = await blob.arrayBuffer()
  const AudioCtx = window.AudioContext || window.webkitAudioContext
  const audioContext = new AudioCtx()
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
  const sampleRate = audioBuffer.sampleRate
  const length = audioBuffer.length
  const samples = new Float32Array(length)
  for (let i = 0; i < length; i++) {
    let sum = 0
    for (let c = 0; c < audioBuffer.numberOfChannels; c++) sum += audioBuffer.getChannelData(c)[i]
    samples[i] = sum / audioBuffer.numberOfChannels
  }
  return new Blob([encodeWav(samples, sampleRate)], { type: 'audio/wav' })
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)        // PCM
  view.setUint16(22, 1, true)        // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, samples.length * 2, true)
  let offset = 44
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
}
