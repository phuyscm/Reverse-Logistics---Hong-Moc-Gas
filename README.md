# H-GAS Reverse Logistics: HFVRP Optimizer

**Tác giả:** Nguyễn Phúc Huy  
**Chuyên ngành:** Quản lý Chuỗi cung ứng và Logistics (Khoa Kỹ thuật Hệ thống Công nghiệp)  
**Trường:** Đại học Bách Khoa TP.HCM (HCMUT) - VNU-HCM  
**Học phần:** Reverse Logistics (Logistics Thu hồi)

---

## 1. Bối Cảnh Nghiệp Vụ (Business Context)
Dự án này được xây dựng dựa trên bài toán thực tế của Doanh nghiệp Hồng Mộc (thương hiệu H-GAS). 

Trong ngành phân phối khí đốt, vỏ bình gas là loại tài sản có giá trị cao, có thể tái sử dụng và đòi hỏi yêu cầu nghiêm ngặt về an toàn[cite: 16, 17]. [cite_start]Với khối lượng vỏ bình lớn và chuỗi cung ứng trải rộng, logistics thu hồi đóng vai trò cực kỳ quan trọng[cite: 37]. [cite_start]Mục tiêu cốt lõi của doanh nghiệp là đảm bảo việc thu hồi vỏ bình diễn ra an toàn, hiệu quả, nhằm giảm thiểu thất thoát tài sản, cắt giảm rác thải và tối ưu hóa chi phí vận hành[cite: 19, 39, 43].

Dự án này số hóa quá trình ra quyết định điều phối xe tải (Routing) thông qua việc giải quyết bài toán **Heterogeneous Fleet Vehicle Routing Problem (HFVRP)** thay cho việc điều xe dựa trên cảm tính và kinh nghiệm truyền thống.

## 2. Luồng Hoạt Động Của Hệ Thống (System Flow)
Ứng dụng được thiết kế với kiến trúc tối ưu, tách biệt rõ ràng giữa Business Logic (Frontend) và Optimization Engine (Backend):

1. **Input Generation (Thiết lập Nhu cầu):** Người dùng (Điều phối viên) chọn các đại lý trên bản đồ (Leaflet.js) và nhập số lượng vỏ bình cần thu hồi.
2. **Smart Fleet Sizing (Hoạch định Đội xe):** Dựa trên tổng nhu cầu, thuật toán Frontend tự động tính toán và đề xuất cấu hình đội xe tối ưu (ví dụ: cần bao nhiêu xe loại 50 vỏ, bao nhiêu xe loại 70 vỏ) để giảm thiểu không gian rỗng (waste capacity).
3. **Graph Processing (Xử lý Đồ thị):** Backend (Python/NetworkX) nhận tọa độ, "snap" (bắt dính) vào mạng lưới đường bộ, cắt Sub-graph và chạy thuật toán Dijkstra đa luồng để lập Ma trận khoảng cách (Distance Matrix).
4. **AI Optimization (Tối ưu hóa Lộ trình):** Lõi Google OR-Tools nhận ma trận, giải quyết mô hình toán học HFVRP với thuật giải `LOCAL_CHEAPEST_INSERTION` để tìm ra tuyến đường có chi phí thấp nhất.
5. **Soft Constraint & Evaluation (Kiểm định SLA):** Trả kết quả về Frontend. Tính toán thời gian thực tế (bao gồm thời gian xe chạy, bốc xếp và chờ đợi) để đối chiếu với cam kết dịch vụ (SLA Limit). Hệ thống xuất báo cáo so sánh trực tiếp hiệu quả của AI so với Baseline (Kinh nghiệm).

## 3. Mô Hình Toán Học (Mathematical Formulation)

Bài toán được mô hình hóa dựa trên mô hình định tuyến xe cơ bản (Vehicle Routing Problem - VRP) từ báo cáo gốc, sau đó được mở rộng thành bài toán **HFVRP (Heterogeneous Fleet VRP)** để giải quyết đặc thù của mạng lưới phân phối và thu hồi vỏ bình gas không đồng nhất.

### Tập hợp và Chỉ số (Sets & Indices)
* $N \in \{0, 1, ..., n\}$: Tập hợp tất cả các điểm (Nodes), với $0$ là Trạm chiết (Depot) và $1..n$ là các khách hàng/đại lý.
* $K \in \{1, 2, ..., m\}$: Tập hợp các phương tiện sẵn có trong hệ thống (Vehicles).
* $k \in K$: Chỉ số của phương tiện.
* $i, j \in N$: Chỉ số của điểm xuất phát và điểm đến.

### Tham số (Parameters)
* $c_{ij}$: Chi phí (khoảng cách) vận hành từ điểm $i$ đến điểm $j$.
* $d_i$: Nhu cầu thu hồi vỏ bình tại đại lý $i$ (với $d_0 = 0$).
* $Q_k$: Sức chứa tối đa (Capacity) của phương tiện $k$.
* $FC_k$: Chi phí cố định (Fixed Cost) khởi động phương tiện $k$ (Mở rộng cho HFVRP).

### Biến Quyết Định (Decision Variables)
* [cite_start]$x_{ijk} \in \{0, 1\}$: Bằng 1 nếu phương tiện $k$ di chuyển từ $i$ đến $j$, ngược lại bằng 0[cite: 157, 158].
* [cite_start]$u_{ik} \ge 0$: Tải trọng tích lũy của phương tiện $k$ ngay sau khi phục vụ điểm $i$[cite: 158].
* $y_k \in \{0, 1\}$: Bằng 1 nếu phương tiện $k$ được đưa vào sử dụng, ngược lại bằng 0.

### Hàm Mục Tiêu (Objective Function)
[cite_start]Tối thiểu hóa tổng chi phí vận hành toàn hệ thống, bao gồm chi phí di chuyển (từ mô hình gốc [cite: 161]) và chi phí cố định của xe (để ép thuật toán giảm số lượng xe):
$$\min Z = \sum_{k \in K} FC_k \cdot y_k + \sum_{k \in K} \sum_{i \in N} \sum_{j \in N, j \neq i} c_{ij} \cdot x_{ijk}$$

### Các Ràng Buộc (Constraints)

**1. Ràng buộc phục vụ khách hàng (Customer Service):**
[cite_start]Đảm bảo mỗi đại lý chỉ được phục vụ đúng một lần bởi một phương tiện duy nhất[cite: 163].
$$\sum_{k \in K} \sum_{i \in N} x_{ijk} = 1 \quad \forall j \in N \setminus \{0\}$$

**2. Ràng buộc bảo toàn luồng (Flow Conservation):**
[cite_start]Nếu phương tiện $k$ đi vào đại lý $h$, nó bắt buộc phải rời khỏi đại lý $h$[cite: 164].
$$\sum_{i \in N} x_{ihk} - \sum_{j \in N} x_{hjk} = 0 \quad \forall h \in N \setminus \{0\}, \forall k \in K$$

**3. Ràng buộc sức chứa và loại trừ vòng lặp phụ (Capacity & Subtour-elimination):**
[cite_start]Đảm bảo tải trọng được cộng dồn chính xác và ngăn chặn xe đi theo các vòng lặp không qua kho[cite: 165].
$$u_{ik} + d_j \cdot x_{ijk} - u_{jk} \le Q_k (1 - x_{ijk}) \quad \forall i, j \in N \setminus \{0\}, i \neq j, \forall k \in K$$

**4. Giới hạn tải trọng tích lũy (Bounds on accumulated load):**
[cite_start]Tải trọng trên xe $k$ sau khi phục vụ điểm $i$ luôn lớn hơn hoặc bằng nhu cầu tại điểm $i$, và không bao giờ vượt quá sức chứa tối đa của chiếc xe đó[cite: 166].
$$d_i \le u_{ik} \le Q_k \quad \forall i \in N \setminus \{0\}, \forall k \in K$$

**5. Ràng buộc xuất phát từ kho (Depot Start):**
[cite_start]Mỗi chiếc xe $k$ chỉ có thể rời khỏi trạm chiết (depot) tối đa một lần[cite: 167]. (Trong HFVRP, nếu xe rời kho, biến $y_k$ sẽ được kích hoạt thành 1).
$$\sum_{j \in N} x_{0jk} = y_k \quad \forall k \in K$$

**6. Ràng buộc kết thúc tại kho (Depot End):**
[cite_start]Đảm bảo nếu chiếc xe $k$ rời khỏi kho thì nó bắt buộc phải quay trở về kho[cite: 167].
$$\sum_{i \in N} x_{i0k} = \sum_{j \in N} x_{0jk} \quad \forall k \in K$$

**7. Miền giá trị của biến quyết định (Variable Domains):**
[cite_start]Đảm bảo giới hạn nhị phân và số thực không âm cho các biến[cite: 168].
$$x_{ijk} \in \{0, 1\} \quad \forall i, j \in N, i \neq j, \forall k \in K$$
$$u_{ik} \ge 0 \quad \forall i \in N, \forall k \in K$$
$$y_k \in \{0, 1\} \quad \forall k \in K$$

---
