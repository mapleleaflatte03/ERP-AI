"""
Analytics Agent Tools - Connects to DB/MinIO for real data
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Global dataframes cache
_dataframes: Dict[str, pd.DataFrame] = {}
_datasets_metadata: Dict[str, Dict] = {}


# ================================================================
# Database Functions (sync wrappers for async DB operations)
# ================================================================

def _run_async(coro):
    """Run async function synchronously"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        # If we're in an async context, we need to run in executor
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)


async def _get_datasets_from_db() -> List[Dict]:
    """Get list of datasets from database"""
    import asyncpg
    
    try:
        conn = await asyncpg.connect('postgresql://erpx:erpx_secret@postgres:5432/erpx')
        rows = await conn.fetch("""
            SELECT id, name, filename, row_count, columns, table_name, minio_bucket, minio_key
            FROM datasets 
            WHERE status = 'ready'
            ORDER BY created_at DESC
        """)
        await conn.close()
        
        datasets = []
        for row in rows:
            cols = json.loads(row["columns"]) if row["columns"] else []
            datasets.append({
                "id": str(row["id"]),
                "name": row["name"] or row["filename"].replace('.csv', '').replace('.xlsx', ''),
                "filename": row["filename"],
                "row_count": row["row_count"],
                "column_count": len(cols),
                "columns": cols if isinstance(cols, list) and isinstance(cols[0] if cols else "", str) else [c.get("name", c) for c in cols],
                "table_name": row["table_name"],
                "minio_bucket": row["minio_bucket"],
                "minio_key": row["minio_key"],
                "source": "database"
            })
        return datasets
    except Exception as e:
        logger.error(f"Failed to get datasets from DB: {e}")
        return []


async def _load_dataset_from_minio(dataset_id: str) -> Optional[pd.DataFrame]:
    """Load dataset file from MinIO"""
    import asyncpg
    import io
    
    try:
        conn = await asyncpg.connect('postgresql://erpx:erpx_secret@postgres:5432/erpx')
        row = await conn.fetchrow(
            "SELECT filename, minio_bucket, minio_key FROM datasets WHERE id = $1",
            dataset_id if isinstance(dataset_id, __import__('uuid').UUID) else __import__('uuid').UUID(dataset_id)
        )
        await conn.close()
        
        if not row:
            return None
        
        # Load from MinIO
        from src.storage import download_document
        file_data = download_document(row["minio_bucket"], row["minio_key"])
        
        filename = row["filename"]
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_data))
        else:
            df = pd.read_excel(io.BytesIO(file_data))
        
        return df
    except Exception as e:
        logger.error(f"Failed to load dataset {dataset_id}: {e}")
        return None


# ================================================================
# Agent Tools Definition
# ================================================================

AGENT_TOOLS = {
    "list_datasets": {
        "description": "Liệt kê tất cả datasets có sẵn trong hệ thống",
        "params": []
    },
    "load_dataset": {
        "description": "Load một dataset vào memory để xử lý",
        "params": ["dataset_name"]
    },
    "describe_dataset": {
        "description": "Xem thống kê và thông tin về dataset",
        "params": ["dataset_name"]
    },
    "get_sample": {
        "description": "Lấy n dòng đầu tiên của dataset",
        "params": ["dataset_name", "n"]
    },
    "filter_data": {
        "description": "Lọc dữ liệu theo điều kiện",
        "params": ["dataset_name", "column", "operator", "value"]
    },
    "aggregate_data": {
        "description": "Tổng hợp dữ liệu theo nhóm",
        "params": ["dataset_name", "group_by", "aggregations"]
    },
    "create_chart": {
        "description": "Tạo biểu đồ từ dữ liệu",
        "params": ["dataset_name", "chart_type", "x_column", "y_column", "title"]
    },
    "create_dashboard": {
        "description": "Tạo dashboard tự động từ dataset",
        "params": ["name", "dataset_name"]
    },
    "list_dashboards": {
        "description": "Liệt kê các dashboard đã tạo",
        "params": []
    }
}

VALID_TOOL_NAMES = set(AGENT_TOOLS.keys())


def get_tools_description() -> str:
    """Get formatted tools description for prompt"""
    lines = ["## Available Tools:"]
    for name, info in AGENT_TOOLS.items():
        params = ", ".join(info["params"]) if info["params"] else ""
        lines.append(f"- {name}({params}): {info['description']}")
    return "\n".join(lines)


# ================================================================
# Agent Tool Executor
# ================================================================

class AgentToolExecutor:
    """Execute agent tools - reads from DB/MinIO"""
    
    def __init__(self):
        self._datasets_cache: Dict[str, Dict] = {}
    
    async def execute(self, tool_name: str, params: Dict[str, Any]) -> Dict:
        """Execute a tool by name"""
        method = getattr(self, f"tool_{tool_name}", None)
        if not method:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return await method(**params)
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _get_dataset_by_name(self, name: str) -> Optional[Dict]:
        """Find dataset by name (case-insensitive)"""
        if not self._datasets_cache:
            datasets = await _get_datasets_from_db()
            for ds in datasets:
                key = ds["name"].lower().replace('.csv', '').replace('.xlsx', '')
                self._datasets_cache[key] = ds
        
        # Try exact match first
        name_lower = name.lower().replace('.csv', '').replace('.xlsx', '')
        if name_lower in self._datasets_cache:
            return self._datasets_cache[name_lower]
        
        # Try partial match
        for key, ds in self._datasets_cache.items():
            if name_lower in key or key in name_lower:
                return ds
        
        return None
    
    async def tool_list_datasets(self) -> Dict:
        """List all available datasets from DB"""
        global _dataframes
        
        datasets = await _get_datasets_from_db()
        
        # Update cache
        self._datasets_cache.clear()
        for ds in datasets:
            key = ds["name"].lower().replace('.csv', '').replace('.xlsx', '')
            self._datasets_cache[key] = ds
        
        return {
            "success": True,
            "count": len(datasets),
            "datasets": [
                {
                    "name": ds["name"],
                    "rows": ds["row_count"],
                    "columns": ds["column_count"],
                    "column_names": ds.get("columns", [])[:5],  # First 5 columns
                    "in_memory": ds["name"].lower() in _dataframes
                }
                for ds in datasets
            ],
            "loaded_in_memory": list(_dataframes.keys())
        }
    
    async def tool_load_dataset(self, dataset_name: str) -> Dict:
        """Load a dataset from DB/MinIO into memory"""
        global _dataframes, _datasets_metadata
        
        name_key = dataset_name.lower().replace('.csv', '').replace('.xlsx', '')
        
        # Check if already loaded
        if name_key in _dataframes:
            df = _dataframes[name_key]
            return {
                "success": True,
                "dataset": name_key,
                "rows": len(df),
                "columns": list(df.columns),
                "already_loaded": True
            }
        
        # Find dataset in DB
        ds_info = await self._get_dataset_by_name(dataset_name)
        if not ds_info:
            return {"error": f"Dataset '{dataset_name}' không tìm thấy trong hệ thống"}
        
        # Load from MinIO
        df = await _load_dataset_from_minio(ds_info["id"])
        if df is None:
            return {"error": f"Không thể load dataset '{dataset_name}' từ storage"}
        
        # Cache it
        _dataframes[name_key] = df
        _datasets_metadata[name_key] = ds_info
        
        return {
            "success": True,
            "dataset": name_key,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)
        }
    
    async def tool_describe_dataset(self, dataset_name: str) -> Dict:
        """Get dataset statistics"""
        name_key = dataset_name.lower().replace('.csv', '').replace('.xlsx', '')
        
        if name_key not in _dataframes:
            result = await self.tool_load_dataset(dataset_name)
            if "error" in result:
                return result
        
        df = _dataframes[name_key]
        
        # Get statistics
        stats = {}
        for col in df.columns:
            col_stats = {"dtype": str(df[col].dtype), "null_count": int(df[col].isnull().sum())}
            if df[col].dtype in ['int64', 'float64']:
                col_stats.update({
                    "min": float(df[col].min()) if not pd.isna(df[col].min()) else None,
                    "max": float(df[col].max()) if not pd.isna(df[col].max()) else None,
                    "mean": round(float(df[col].mean()), 2) if not pd.isna(df[col].mean()) else None,
                    "sum": float(df[col].sum()) if not pd.isna(df[col].sum()) else None
                })
            else:
                col_stats["unique"] = int(df[col].nunique())
            stats[col] = col_stats
        
        return {
            "success": True,
            "dataset": name_key,
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": list(df.columns),
            "statistics": stats
        }
    
    async def tool_get_sample(self, dataset_name: str, n: int = 5) -> Dict:
        """Get sample rows"""
        name_key = dataset_name.lower().replace('.csv', '').replace('.xlsx', '')
        
        if name_key not in _dataframes:
            result = await self.tool_load_dataset(dataset_name)
            if "error" in result:
                return result
        
        df = _dataframes[name_key]
        n = min(int(n) if isinstance(n, str) else n, 20)  # Max 20 rows
        sample = df.head(n)
        
        return {
            "success": True,
            "dataset": name_key,
            "total_rows": len(df),
            "sample_rows": n,
            "columns": list(sample.columns),
            "data": sample.to_dict(orient='records')
        }
    
    async def tool_filter_data(self, dataset_name: str, column: str, 
                               operator: str, value: Any) -> Dict:
        """Filter dataset"""
        name_key = dataset_name.lower().replace('.csv', '').replace('.xlsx', '')
        
        if name_key not in _dataframes:
            result = await self.tool_load_dataset(dataset_name)
            if "error" in result:
                return result
        
        df = _dataframes[name_key]
        
        if column not in df.columns:
            return {"error": f"Column '{column}' không tồn tại. Columns có: {list(df.columns)}"}
        
        try:
            if operator in ["==", "="]:
                filtered = df[df[column] == value]
            elif operator == "!=":
                filtered = df[df[column] != value]
            elif operator == ">":
                filtered = df[df[column] > float(value)]
            elif operator == "<":
                filtered = df[df[column] < float(value)]
            elif operator == ">=":
                filtered = df[df[column] >= float(value)]
            elif operator == "<=":
                filtered = df[df[column] <= float(value)]
            elif operator in ["contains", "like"]:
                filtered = df[df[column].astype(str).str.contains(str(value), case=False, na=False)]
            else:
                return {"error": f"Operator '{operator}' không được hỗ trợ"}
            
            # Save filtered result
            filtered_name = f"{name_key}_filtered"
            _dataframes[filtered_name] = filtered
            
            return {
                "success": True,
                "original_rows": len(df),
                "filtered_rows": len(filtered),
                "percentage": round(len(filtered) / len(df) * 100, 1),
                "saved_as": filtered_name,
                "sample": filtered.head(5).to_dict(orient='records')
            }
        except Exception as e:
            return {"error": f"Lỗi filter: {str(e)}"}
    
    async def tool_aggregate_data(self, dataset_name: str, group_by: str, 
                                   aggregations: str) -> Dict:
        """Aggregate data by grouping
        
        Args:
            aggregations: Format "col:func,col:func" e.g. "Volume:sum,Close:mean"
        """
        name_key = dataset_name.lower().replace('.csv', '').replace('.xlsx', '')
        
        if name_key not in _dataframes:
            result = await self.tool_load_dataset(dataset_name)
            if "error" in result:
                return result
        
        df = _dataframes[name_key]
        
        if group_by not in df.columns:
            return {"error": f"Column '{group_by}' không tồn tại"}
        
        try:
            # Parse aggregations
            agg_dict = {}
            for agg in aggregations.split(','):
                parts = agg.strip().split(':')
                if len(parts) == 2:
                    col, func = parts
                    if col.strip() in df.columns:
                        agg_dict[col.strip()] = func.strip()
            
            if not agg_dict:
                return {"error": "Không có aggregation hợp lệ"}
            
            result = df.groupby(group_by).agg(agg_dict).reset_index()
            
            # Rename columns
            new_cols = [group_by]
            for col, func in agg_dict.items():
                new_cols.append(f"{col}_{func}")
            result.columns = new_cols
            
            # Save result
            result_name = f"{name_key}_agg"
            _dataframes[result_name] = result
            
            return {
                "success": True,
                "groups": len(result),
                "columns": list(result.columns),
                "saved_as": result_name,
                "data": result.to_dict(orient='records')
            }
        except Exception as e:
            return {"error": f"Lỗi aggregate: {str(e)}"}
    
    async def tool_create_chart(self, dataset_name: str, chart_type: str,
                                x_column: str, y_column: str, title: str = None) -> Dict:
        """Create a chart configuration"""
        name_key = dataset_name.lower().replace('.csv', '').replace('.xlsx', '')
        
        if name_key not in _dataframes:
            result = await self.tool_load_dataset(dataset_name)
            if "error" in result:
                return result
        
        df = _dataframes[name_key]
        
        # Validate columns
        if x_column not in df.columns:
            return {"error": f"Column '{x_column}' không tồn tại"}
        if y_column not in df.columns:
            return {"error": f"Column '{y_column}' không tồn tại"}
        
        # Prepare chart data
        chart_df = df[[x_column, y_column]].dropna()
        if len(chart_df) > 100:
            # Aggregate if too many points
            if df[x_column].dtype == 'object':
                chart_df = chart_df.groupby(x_column)[y_column].mean().reset_index()
            else:
                chart_df = chart_df.head(100)
        
        return {
            "success": True,
            "chart": {
                "type": chart_type,
                "title": title or f"{y_column} by {x_column}",
                "x_field": x_column,
                "y_field": y_column,
                "data_points": len(chart_df),
                "data": chart_df.to_dict(orient='records')
            }
        }
    
    async def tool_create_dashboard(self, name: str, dataset_name: str) -> Dict:
        """Create a dashboard from dataset"""
        from ..engine.dashboard_service import get_dashboard_service
        
        name_key = dataset_name.lower().replace('.csv', '').replace('.xlsx', '')
        
        if name_key not in _dataframes:
            result = await self.tool_load_dataset(dataset_name)
            if "error" in result:
                return result
        
        df = _dataframes[name_key]
        service = get_dashboard_service()
        
        try:
            # Find date column
            date_col = None
            for col in df.columns:
                if 'date' in col.lower() or 'time' in col.lower():
                    date_col = col
                    break
            
            dashboard = service.auto_create_dashboard(
                name=name,
                dataset_name=name_key,
                df=df,
                date_column=date_col
            )
            
            return {
                "success": True,
                "dashboard_id": dashboard.dashboard_id,
                "name": dashboard.name,
                "charts": len(dashboard.charts),
                "metrics": len(dashboard.metrics),
                "message": f"Dashboard '{name}' đã được tạo với {len(dashboard.charts)} biểu đồ và {len(dashboard.metrics)} metrics"
            }
        except Exception as e:
            return {"error": f"Lỗi tạo dashboard: {str(e)}"}
    
    async def tool_list_dashboards(self) -> Dict:
        """List all dashboards"""
        from ..engine.dashboard_service import get_dashboard_service
        service = get_dashboard_service()
        dashboards = service.list_dashboards()
        return {
            "success": True,
            "count": len(dashboards),
            "dashboards": dashboards
        }


# ================================================================
# Tool Parser
# ================================================================

def parse_tool_call(response: str) -> Optional[Tuple[str, Dict]]:
    """Parse tool call from LLM response - supports both JSON and function-call formats"""
    import json as json_module
    
    # Method 1: Try JSON format in ```tool block
    json_pattern = r'```tool\s*\n?\s*(\{[^`]+\})\s*\n?```'
    match = re.search(json_pattern, response, re.DOTALL)
    if match:
        try:
            data = json_module.loads(match.group(1).strip())
            tool_name = data.get("name", "")
            params = data.get("params", {})
            if tool_name in VALID_TOOL_NAMES:
                return tool_name, params
        except json_module.JSONDecodeError:
            pass
    
    # Method 2: Try JSON object directly {"name": "...", "params": {...}}
    json_direct_pattern = r'\{"name":\s*"(\w+)".*?"params":\s*(\{[^}]*\})'
    match = re.search(json_direct_pattern, response, re.DOTALL)
    if match:
        try:
            tool_name = match.group(1)
            params = json_module.loads(match.group(2))
            if tool_name in VALID_TOOL_NAMES:
                return tool_name, params
        except json_module.JSONDecodeError:
            pass
    
    # Method 3: Try function-call format: tool_name(params)
    tool_names_pattern = "|".join(VALID_TOOL_NAMES)
    pattern = rf'({tool_names_pattern})\s*\((.*?)\)'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        tool_name = match.group(1)
        params_str = match.group(2).strip()
        
        params = {}
        if params_str:
            # Try parsing as JSON first
            try:
                params = json_module.loads("{" + params_str + "}")
            except:
                # Parse key='value' or key="value"
                param_pattern = r'(\w+)\s*=\s*[\'"]?([^\'"(),]+)[\'"]?'
                for m in re.finditer(param_pattern, params_str):
                    key = m.group(1)
                    value = m.group(2).strip()
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                    params[key] = value
        
        return tool_name, params
    
    return None


def get_tool_executor() -> AgentToolExecutor:
    """Get tool executor instance"""
    return AgentToolExecutor()
