import {useEffect, useState} from 'react';
import type {QueryResponse} from './api/types';

type Props = {
  result: QueryResponse;
  busy: boolean;
  onSubmit: (query: string) => void;
};

export default function QueryRefinementCard({result, busy, onSubmit}: Props) {
  const [text, setText] = useState(result.query);
  useEffect(() => setText(result.query), [result.query]);
  const hasPeriod = Boolean(result.period?.start && result.period?.end);

  return <section className="agent-recovery query-refinement-card" aria-label="지표 확인 질문">
    <h2>조회할 지표를 조금 더 확인할게요</h2>
    <p>{result.refinementQuestion}</p>
    <p>{hasPeriod
      ? `확인한 조회 기간: ${result.period.start} ~ ${result.period.end}. 지표명이나 통계표 이름을 보완해 주세요.`
      : '지표명이나 통계표 이름을 보완해 주세요.'}</p>
    <label>보완할 질문
      <textarea aria-label="지표명과 기준을 보완할 질문" value={text}
        onChange={event => setText(event.target.value)} disabled={busy}/>
    </label>
    <button type="button" disabled={busy || !text.trim() || text.trim() === result.query.trim()}
      onClick={() => onSubmit(text.trim())}>
      {busy ? '확인 중…' : '보완한 질문으로 조회'}
    </button>
  </section>;
}
