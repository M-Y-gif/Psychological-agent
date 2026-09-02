// 后端 API 封装
const BASE = '/api'

export async function chat(question, emotionContext) {
  const body = { question }
  if (emotionContext) body.emotionContext = emotionContext
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}

export async function multimodalAnalyze(audioFile, imageFile) {
  const fd = new FormData()
  if (audioFile) fd.append('audio', audioFile)
  if (imageFile) fd.append('image', imageFile)
  const res = await fetch(`${BASE}/multimodal/analyze`, { method: 'POST', body: fd })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}
