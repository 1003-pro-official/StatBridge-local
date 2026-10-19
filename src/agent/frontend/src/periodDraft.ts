/** Read submitted date controls, not a possibly stale render closure. */
export function periodDraft(data:{get:(name:string)=>unknown}) {
 const start=String(data.get('period_start')??''),end=String(data.get('period_end')??'');
 const valid=(value:string)=>/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value+'T00:00:00Z'))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
 if(!valid(start)||!valid(end)||start>end)throw new Error('시작일과 종료일을 올바른 순서로 입력해 주세요.');
 return {start,end,instruction:`기간을 ${start}부터 ${end}까지로 변경해줘`};
}
