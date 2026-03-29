import { useApp } from '../store'

// 마크다운 텍스트를 보기 좋게 렌더링하는 공유 컴포넌트
export default function MdResult({ text, loading }: { text: string; loading: boolean }) {
  const { t } = useApp()
  if (loading) return (
    <p className="text-gray-500 text-sm animate-pulse">{t('md_long_analyzing')}</p>
  )
  if (!text) return (
    <p className="text-gray-600 text-sm">{t('md_start_hint')}</p>
  )
  return (
    <div className="space-y-0.5">
      {text.split('\n').map((line, i) => {
        if (line.startsWith('# '))
          return <h2 key={i} className="text-base font-bold text-white mt-3 mb-1">{line.slice(2)}</h2>
        if (line.startsWith('## '))
          return <h3 key={i} className="text-sm font-semibold text-emerald-400 mt-3 mb-1 border-b border-gray-800 pb-1">{line.slice(3)}</h3>
        if (line.startsWith('### '))
          return <h4 key={i} className="text-sm font-medium text-yellow-400 mt-2 mb-0.5">{line.slice(4)}</h4>
        if (line.startsWith('- '))
          return <p key={i} className="text-sm text-gray-300 pl-3">• {line.slice(2)}</p>
        if (line.startsWith('  - '))
          return <p key={i} className="text-sm text-gray-400 pl-6">· {line.slice(4)}</p>
        if (line.startsWith('| '))
          return <p key={i} className="text-xs font-mono text-gray-400 pl-2">{line}</p>
        if (line.startsWith('```'))
          return null
        if (line.trim() === '') return <div key={i} className="h-1.5" />
        return <p key={i} className="text-sm text-gray-400">{line}</p>
      })}
    </div>
  )
}
