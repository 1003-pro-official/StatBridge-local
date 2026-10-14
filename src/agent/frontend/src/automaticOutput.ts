import type {OutputRenderRequest, QueryResponse} from './api/types';

// Use the server's capabilities; never reinterpret table IDs or query words here.
export function automaticOutput(result:QueryResponse):OutputRenderRequest|null {
 if(result.status!=='need_output_config')return null;
 const ids=result.outputSessionIds||[result.outputSessionId||''].filter(Boolean);
 if(!ids.length||!result.outputOptions?.supportedChartTypes.length)return null;
 return {session_ids:ids,chart_type:'auto',chart_mode:result.outputOptions.combinedLayoutReason?'separate':'combined',show_legend:true,natural_language:result.query,quick_output:true};
}
