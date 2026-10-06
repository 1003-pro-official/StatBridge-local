import type {QueryRequest} from './api/types';

// Interpretation belongs to the authoritative backend, not UI keyword heuristics.
export function initialQueryRequest(text:string):QueryRequest {
  return {query:text.trim(),execute:true};
}
