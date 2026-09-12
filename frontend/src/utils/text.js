/**
 * 兜底清洗模型输出：提示词已要求纯段落口语，但模型偶尔仍会带 markdown 标记，
 * 这里把符号去掉、保留文字，保证界面上不会露出 ** 、- 这类记号。
 */
export function plainText(input) {
  if (!input) return ''
  let s = String(input).replace(/\r\n/g, '\n')
  s = s.replace(/```[a-zA-Z]*\n?/g, '')          // 代码围栏
  s = s.replace(/^\s{0,3}#{1,6}\s+/gm, '')        // # 标题
  s = s.replace(/\*\*([^*]+)\*\*/g, '$1')         // **粗体**
  s = s.replace(/\*([^*\n]+)\*/g, '$1')           // *斜体*
  s = s.replace(/__([^_]+)__/g, '$1')             // __粗体__
  s = s.replace(/`([^`\n]+)`/g, '$1')             // `行内代码`
  s = s.replace(/^\s{0,3}>\s?/gm, '')             // > 引用
  s = s.replace(/^\s{0,3}[-*+]\s+/gm, '')         // - 无序列表
  s = s.replace(/^\s{0,3}\d+[.)]\s+/gm, '')       // 1. 有序列表
  s = s.replace(/^\s*([-*_]\s*){3,}$/gm, '')      // --- 分隔线
  s = s.replace(/[ \t]+\n/g, '\n')
  s = s.replace(/\n{3,}/g, '\n\n')
  return s.trim()
}
