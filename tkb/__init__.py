"""Xếp thời khóa biểu (xem CLAUDE.md, docs/Dac_Ta_Nghiep_Vu_TKB_V16.md)."""
from . import config, luat_co_san

# Mọi luật xếp bằng bộ ghép, kể cả khi chưa đọc file nào: giá trị mặc định của config là các dòng mặc định của sheet
# LUẬT (luat_co_san.apply), như một file có sheet LUẬT ghi đúng các dòng đó, nên hai cách cùng mô hình, cùng mã.
for _attr, _value in luat_co_san.apply(luat_co_san.default_rows()).items():
    setattr(config, _attr, _value)
del _attr, _value
