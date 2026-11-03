"""vNext compatibility entry point; strengthened scorer is mandatory."""
from legacy_score_core import compare_state,compare_rows,source_key,read_cases
from score_reviewed import score as score_case,main
if __name__=="__main__":main()
