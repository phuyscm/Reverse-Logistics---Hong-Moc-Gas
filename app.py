from flask import Flask, render_template, request, jsonify
import pandas as pd
import networkx as nx
import shapely.wkt
from scipy.spatial import KDTree
from concurrent.futures import ThreadPoolExecutor
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

app = Flask(__name__)

print("🚀 Đang khởi động hệ thống Reverse Logistics HFVRP...")
nodes_df = pd.read_csv("hcm_nodes.csv", low_memory=False)
edges_df = pd.read_csv("hcm_edges.csv", low_memory=False)
edges_truck = edges_df[~edges_df['highway'].isin(['footway', 'pedestrian', 'path', 'cycleway', 'steps'])].copy()

G_full = nx.MultiDiGraph()
for _, row in nodes_df.iterrows():
    G_full.add_node(row['osmid'], y=row['y'], x=row['x'])
for _, row in edges_truck.iterrows():
    geom = shapely.wkt.loads(row['geometry'])
    name = str(row.get('name', 'Đường không tên'))
    if name == 'nan': name = 'Đường không tên'
    G_full.add_edge(row['u'], row['v'], weight=row['length'], geometry=geom, name=name)

tree = KDTree(nodes_df[['y', 'x']].values)

def compute_dijkstra(args):
    G_sub, src, dst, i, j = args
    try:
        d, path = nx.single_source_dijkstra(G_sub, src, dst, weight='weight')
        return (i, j, d, path)
    except: return (i, j, None, None)

def calculate_baseline(dist_matrix, demands, fleet, n):
    unvisited = set(range(1, n))
    current_node = 0
    current_load = 0
    total_dist = 0
    vehicles_used = 1
    
    fleet_sorted = sorted(fleet, reverse=True)
    if not fleet_sorted: return 0, 0
    
    current_capacity = fleet_sorted[0]
    
    while unvisited:
        nearest = None
        min_dist = float('inf')
        for candidate in unvisited:
            d = dist_matrix[current_node][candidate]
            if d < min_dist:
                min_dist = d
                nearest = candidate
                
        if current_load + demands[nearest] <= current_capacity:
            total_dist += min_dist
            current_load += demands[nearest]
            current_node = nearest
            unvisited.remove(nearest)
        else:
            total_dist += dist_matrix[current_node][0]
            current_node = 0
            current_load = 0
            vehicles_used += 1
            if vehicles_used <= len(fleet_sorted):
                current_capacity = fleet_sorted[vehicles_used-1]
            else:
                current_capacity = fleet_sorted[0] 
            
    total_dist += dist_matrix[current_node][0]
    return total_dist, vehicles_used

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/optimize', methods=['POST'])
def optimize():
    try:
        data = request.json
        points, addresses = data['points'], data['addresses']
        velocity = float(data.get('velocity', 30))
        demands = data.get('demands', [0] + [20] * (len(points) - 1))
        
        vehicle_capacities = data.get('fleet', [])
        if not vehicle_capacities:
            return jsonify({'status': 'error', 'message': 'Chưa có nhu cầu vận chuyển.'})

        max_cap = max(vehicle_capacities)
        if any(d > max_cap for d in demands):
            return jsonify({'status': 'error', 'message': f'Lỗi: Có đại lý yêu cầu số vỏ vượt quá sức chứa xe to nhất ({max_cap} vỏ).'})

        vehicle_capacities.extend([max_cap, max_cap])
        num_vehicles = len(vehicle_capacities)

        target_nodes = []
        for pt in points:
            _, idx = tree.query(pt)
            target_nodes.append(nodes_df.iloc[idx]['osmid'])

        snapped_lats = [G_full.nodes[n]['y'] for n in target_nodes]
        snapped_lons = [G_full.nodes[n]['x'] for n in target_nodes]
        
        # NỚI RỘNG KHUNG BẢN ĐỒ LÊN 9KM ĐỂ TRÁNH ĐỨT ĐƯỜNG 1 CHIỀU
        margin = 0.08 
        sub_nodes = [n for n, d in G_full.nodes(data=True) if min(snapped_lats)-margin <= d['y'] <= max(snapped_lats)+margin and min(snapped_lons)-margin <= d['x'] <= max(snapped_lons)+margin]
        G = G_full.subgraph(sub_nodes).copy()

        n = len(target_nodes)
        tasks = [(G, target_nodes[i], target_nodes[j], i, j) for i in range(n) for j in range(n) if i != j]
        dist_dict, path_matrix = {}, {}
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(compute_dijkstra, tasks))
        
        dist_matrix_2d = [[0] * n for _ in range(n)]
        for i, j, d, path in results:
            if d is not None:
                dist_dict[(i, j)] = d
                path_matrix[(i, j)] = path
                dist_matrix_2d[i][j] = int(d)
            else:
                dist_matrix_2d[i][j] = 99999999 # Khoảng cách cực lớn cho điểm không có đường

        base_dist, base_vehicles = calculate_baseline(dist_matrix_2d, demands, vehicle_capacities[:-2], n)

        manager = pywrapcp.RoutingIndexManager(n, num_vehicles, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            return dist_matrix_2d[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

        dist_cb = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(dist_cb)

        def demand_callback(from_index):
            return demands[manager.IndexToNode(from_index)]

        demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_cb, 0, vehicle_capacities, True, "Capacity"
        )

        # LỚP GIÁP 2: Chấp nhận bỏ điểm nếu điểm đó bị cô lập hoàn toàn (Phạt 5 triệu)
        penalty = 5000000
        for node in range(1, n):
            routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.LOCAL_CHEAPEST_INSERTION
        search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        search_params.time_limit.seconds = 3 

        solution = routing.SolveWithParameters(search_params)

        if not solution:
            return jsonify({'status': 'error', 'message': 'Hệ thống bế tắc do vị trí các đại lý quá rời rạc không thể ghép chuyến. Vui lòng thử lại!'})

        dropped_nodes = []
        for node in range(1, n):
            if solution.Value(routing.NextVar(manager.NodeToIndex(node))) == manager.NodeToIndex(node):
                dropped_nodes.append(node)
                
        if dropped_nodes:
            dropped_addrs = [addresses[i] for i in dropped_nodes]
            return jsonify({'status': 'error', 'message': f'⚠️ Cảnh báo: AI đã tự động loại bỏ {len(dropped_nodes)} đại lý do bị cô lập hoàn toàn (không có đường đi): {", ".join(dropped_addrs)}. Vui lòng xóa bớt!'})

        vehicles_routes = []
        total_sys_distance = 0
        ai_vehicles_used = 0
        
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            if routing.IsEnd(solution.Value(routing.NextVar(index))): continue 
            
            ai_vehicles_used += 1
            route_nodes, route_load, route_dist = [], 0, 0
            
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                route_nodes.append(node)
                route_load += demands[node]
                next_idx = solution.Value(routing.NextVar(index))
                route_dist += routing.GetArcCostForVehicle(index, next_idx, vehicle_id)
                index = next_idx
            
            route_nodes.append(0) 
            total_sys_distance += route_dist
            
            num_stops = len(route_nodes) - 2 
            travel_time_mins = (route_dist/1000) / velocity * 60
            handling_time_mins = route_load * 0.5 
            buffer_time_mins = num_stops * 15 
            
            total_time_mins = round(travel_time_mins + handling_time_mins + buffer_time_mins)
            
            segments, itinerary = [], []
            for i in range(len(route_nodes)-1):
                u_idx, v_idx = route_nodes[i], route_nodes[i+1]
                node_path = path_matrix.get((u_idx, v_idx), [])
                if node_path:
                    seg_coords = [[G.nodes[node]['y'], G.nodes[node]['x']] for node in node_path]
                    segments.append(seg_coords)
                    streets = []
                    for k in range(len(node_path)-1):
                        s_name = G.get_edge_data(node_path[k], node_path[k+1])[0].get('name', 'Đường nội bộ')
                        if not streets or streets[-1] != s_name: streets.append(s_name)
                    itinerary.append({"from_addr": addresses[u_idx], "to_addr": addresses[v_idx], "streets": " ➔ ".join(streets)})
            
            vehicles_routes.append({
                'vehicle_id': vehicle_id + 1,
                'capacity': vehicle_capacities[vehicle_id],
                'order': route_nodes,
                'load': route_load,
                'distance_km': round(route_dist/1000, 2),
                'time_mins': total_time_mins, 
                'segments': segments,
                'itinerary': itinerary
            })

        return jsonify({
            'status': 'success', 
            'total_sys_km': round(total_sys_distance/1000, 2),
            'ai_vehicles_used': ai_vehicles_used,
            'base_km': round(base_dist/1000, 2),
            'base_vehicles': base_vehicles,
            'vehicles': vehicles_routes
        })

    except Exception as e: 
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)