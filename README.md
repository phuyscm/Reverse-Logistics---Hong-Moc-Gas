# 🚚 H-GAS Reverse Logistics: HFVRP Optimizer

**Tác giả:** Nguyễn Phúc Huy  
**Chuyên ngành:** Quản lý Chuỗi cung ứng và Logistics (Khoa Kỹ thuật Hệ thống Công nghiệp)  
**Trường:** Đại học Bách Khoa TP.HCM (HCMUT) - VNU-HCM  
**Học phần:** Reverse Logistics (Logistics Thu hồi)

---

## 1. Bối Cảnh Nghiệp Vụ (Business Context)
Dự án này được xây dựng dựa trên bài toán thực tế của Doanh nghiệp Hồng Mộc (thương hiệu H-GAS). 

[cite_start]Trong ngành phân phối khí đốt, vỏ bình gas là loại tài sản có giá trị cao, có thể tái sử dụng và đòi hỏi yêu cầu nghiêm ngặt về an toàn[cite: 16, 17]. [cite_start]Với khối lượng vỏ bình lớn và chuỗi cung ứng trải rộng, logistics thu hồi đóng vai trò cực kỳ quan trọng[cite: 37]. [cite_start]Mục tiêu cốt lõi của doanh nghiệp là đảm bảo việc thu hồi vỏ bình diễn ra an toàn, hiệu quả, nhằm giảm thiểu thất thoát tài sản, cắt giảm rác thải và tối ưu hóa chi phí vận hành[cite: 19, 39, 43].

Dự án này số hóa quá trình ra quyết định điều phối xe tải (Routing) thông qua việc giải quyết bài toán **Heterogeneous Fleet Vehicle Routing Problem (HFVRP)** thay cho việc điều xe dựa trên cảm tính và kinh nghiệm truyền thống.

## 2. Luồng Hoạt Động Của Hệ Thống (System Flow)
Ứng dụng được thiết kế với kiến trúc tối ưu, tách biệt rõ ràng giữa Business Logic (Frontend) và Optimization Engine (Backend):

1. **Input Generation (Thiết lập Nhu cầu):** Người dùng (Điều phối viên) chọn các đại lý trên bản đồ (Leaflet.js) và nhập số lượng vỏ bình cần thu hồi.
2. **Smart Fleet Sizing (Hoạch định Đội xe):** Dựa trên tổng nhu cầu, thuật toán Frontend tự động tính toán và đề xuất cấu hình đội xe tối ưu (ví dụ: cần bao nhiêu xe loại 50 vỏ, bao nhiêu xe loại 70 vỏ) để giảm thiểu không gian rỗng (waste capacity).
3. **Graph Processing (Xử lý Đồ thị):** Backend (Python/NetworkX) nhận tọa độ, "snap" (bắt dính) vào mạng lưới đường bộ, cắt Sub-graph và chạy thuật toán Dijkstra đa luồng để lập Ma trận khoảng cách (Distance Matrix).
4. **AI Optimization (Tối ưu hóa Lộ trình):** Lõi Google OR-Tools nhận ma trận, giải quyết mô hình toán học HFVRP với thuật giải `LOCAL_CHEAPEST_INSERTION` để tìm ra tuyến đường có chi phí thấp nhất.
5. **Soft Constraint & Evaluation (Kiểm định SLA):** Trả kết quả về Frontend. Tính toán thời gian thực tế (bao gồm thời gian xe chạy, bốc xếp và chờ đợi) để đối chiếu với cam kết dịch vụ (SLA Limit). Hệ thống xuất báo cáo so sánh trực tiếp hiệu quả của AI so với Baseline (Kinh nghiệm).

## 3. Mô Hình Toán Học (Mathematical Formulation)
Bài toán tối ưu hóa của H-GAS được mô hình hóa dưới dạng HFVRP nhằm tối thiểu hóa tổng chi phí vận hành (bao gồm chi phí cố định mở xe và chi phí di chuyển).

### Tập hợp và Chỉ số (Sets & Indices)
* $N$: Tập hợp tất cả các điểm (Nodes), với $0$ là Trạm chiết (Depot) và $1, ..., n$ là các đại lý.
* $V$: Tập hợp các phương tiện sẵn có trong hệ thống (Vehicles), với các mức tải trọng khác nhau.

### Tham số (Parameters)
* $c_{ij}$: Chi phí vận hành từ điểm $i$ đến điểm $j$ (tính toán từ Ma trận Dijkstra).
* $FC_k$: Chi phí cố định (Fixed Cost) khi quyết định khởi động phương tiện $k$.
* $Q_k$: Sức chứa tối đa (Capacity) của phương tiện $k$.
* $d_i$: Nhu cầu thu hồi vỏ bình tại đại lý $i$ ($d_0 = 0$).

### Biến Quyết Định (Decision Variables)
* $x_{ijk} \in \{0, 1\}$: Bằng 1 nếu phương tiện $k$ di chuyển trực tiếp từ $i$ đến $j$, ngược lại bằng 0.
* $y_k \in \{0, 1\}$: Bằng 1 nếu phương tiện $k$ được đưa vào sử dụng, ngược lại bằng 0.

### Hàm Mục Tiêu (Objective Function)
Tối thiểu hóa tổng chi phí vận hành toàn hệ thống:
$$\min Z = \sum_{k \in V} FC_k \cdot y_k + \sum_{k \in V} \sum_{i \in N} \sum_{j \in N, j \neq i} c_{ij} \cdot x_{ijk}$$

### Các Ràng Buộc Trọng Yếu (Key Constraints)

**1. Đảm bảo năng lực chuyên chở (Capacity Constraint):**
Tổng lượng vỏ bình thu hồi trên một tuyến đường không được vượt quá tải trọng của xe được điều động.
$$\sum_{i \in N} d_i \sum_{j \in N} x_{ijk} \leq Q_k \cdot y_k \quad \forall k \in V$$

**2. Ràng buộc bảo toàn luồng (Flow Conservation):**
Nếu phương tiện $k$ đi vào đại lý $h$, nó bắt buộc phải rời khỏi đại lý $h$.
$$\sum_{i \in N} x_{ihk} - \sum_{j \in N} x_{hjk} = 0 \quad \forall h \in N \setminus \{0\}, \forall k \in V$$

**3. Ràng buộc phục vụ duy nhất (Single Visit Constraint):**
Mỗi đại lý có nhu cầu thu hồi chỉ được phục vụ đúng một lần bởi một phương tiện duy nhất.
$$\sum_{k \in V} \sum_{i \in N} x_{ijk} = 1 \quad \forall j \in N \setminus \{0\}$$

---
*(Phần Hướng dẫn Cài đặt, Cấu trúc Code và Báo cáo Kiểm định Validation sẽ được cập nhật sau).*
