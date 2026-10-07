"""Record original-file candidate probes for report types not selected in v2."""
import re

from common import BASE, ROOT, csv_rows, digest, write_json


def main():
    import openpyxl
    from pypdf import PdfReader
    research = csv_rows(ROOT / "research/그림표-분석/그림표_마스터.csv")
    probes = []
    for report_type in ("연차보고서", "지급결제보고서"):
        candidates = [r for r in research if r["보고서"].startswith(report_type)]
        row = next(r for r in candidates if (".xlsx" in r["근거"] if report_type == "지급결제보고서" else "PDF p." in r["근거"]))
        if report_type == "지급결제보고서":
            filename = re.search(r"([^;]+\.xlsx)", row["근거"])[1].strip()
            sheet = re.search(r"xlsx:([^;]+)", row["근거"])[1]
            paths = list((ROOT / "research/bok-archive").rglob(filename))
            if len(paths) != 1:
                raise ValueError("candidate original unavailable")
            book = openpyxl.load_workbook(paths[0], read_only=True, data_only=True)
            values = list(book[sheet].iter_rows(min_row=1, max_row=12, max_col=6, values_only=True))
            text = " ".join(str(v) for r in values for v in r if isinstance(v, str))
            locator = sheet + "!A1:F12"
        else:
            filename = row["근거"].split(";")[0]
            page = int(re.search(r"PDF p\.(\d+)", row["근거"])[1])
            paths = list((ROOT / "research/bok-archive").rglob(filename))
            if len(paths) != 1:
                raise ValueError("candidate original unavailable")
            text = PdfReader(paths[0]).pages[page-1].extract_text() or ""
            locator = "PDF page " + str(page)
        compact = lambda s: re.sub(r"\s+", "", s)
        probes.append({"report_type": report_type, "research_result_id": row["결과물ID"],
            "original": paths[0].relative_to(ROOT).as_posix(), "sha256": digest(paths[0]), "locator": locator,
            "title": row["제목"], "title_observed": compact(row["제목"]) in compact(text),
            "selected": False,
            "reason": "Candidate inspected only; independent numeric extraction and supported-series mapping not completed. Do not promote inferred metadata to gold."})
    write_json(BASE / "candidate_probes.json", probes)


if __name__ == "__main__":
    main()
