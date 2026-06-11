from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from agent_app.domain.models import DataAuditReport


class DataAnalysisService:
    def audit_files(self, files: list[Path]) -> DataAuditReport:
        report = DataAuditReport()
        for path in files:
            path = Path(path)
            report.files.append(path.name)
            suffix = path.suffix.lower()
            if suffix == ".csv":
                self._audit_frame(pd.read_csv(path), report)
            elif suffix in {".xlsx", ".xls"}:
                try:
                    self._audit_frame(pd.read_excel(path), report)
                except Exception as exc:
                    report.data_limitations.append(f"{path.name}: Excel 读取失败: {exc}")
            else:
                report.data_limitations.append(f"{path.name}: 当前仅记录文件，未做表格审计")
        return report

    def _audit_frame(self, df: pd.DataFrame, report: DataAuditReport) -> None:
        for column in df.columns:
            series = df[column]
            report.field_dictionary[str(column)] = str(series.dtype)
            report.missing_values[str(column)] = int(series.isna().sum())
            if str(column) not in report.usable_features:
                report.usable_features.append(str(column))
            if pd.api.types.is_numeric_dtype(series):
                stats = series.describe().to_dict()
                report.descriptive_statistics[str(column)] = {
                    key: _jsonable(value) for key, value in stats.items()
                }

    def to_markdown(self, report: DataAuditReport) -> str:
        lines = ["# 数据审计报告", ""]
        lines.append("## 文件")
        lines.extend(f"- {name}" for name in report.files)
        lines.append("")
        lines.append("## 字段")
        for name, dtype in report.field_dictionary.items():
            missing = report.missing_values.get(name, 0)
            lines.append(f"- `{name}`: {dtype}, 缺失值 {missing}")
        lines.append("")
        lines.append("## 可用特征")
        lines.extend(f"- `{name}`" for name in report.usable_features)
        if report.data_limitations:
            lines.append("")
            lines.append("## 数据限制")
            lines.extend(f"- {item}" for item in report.data_limitations)
        return "\n".join(lines) + "\n"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value
