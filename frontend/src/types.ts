export type ExtractionPayload = {
  bbox: [number, number, number, number]
  date: string
  location_name: string
  project_id?: string
  run_fetch?: boolean
  fetch_only?: boolean
  scene_path?: string
  masked_path?: string
  tile_dir?: string
  sr_tile_dir?: string
  sr_model_path?: string
  drive_folder?: string
  cloud_filter_pct?: number
  ndwi_threshold?: number
  tile_size?: number
  stride?: number
  black_threshold?: number
  blur_threshold?: number
  download_scene?: boolean
  annotate_ships?: boolean
  ship_min_area_px?: number
  ship_max_area_px?: number
  ship_min_intensity?: number
  ship_threshold_percentile?: number
}

export type BatchLocation = {
  name: string
  bbox: [number, number, number, number]
}

export type BatchExtractionPayload = {
  locations: BatchLocation[]
  dates: string[]
  project_id?: string
  run_fetch?: boolean
  fetch_only?: boolean
  download_scene?: boolean
  drive_folder?: string
  cloud_filter_pct?: number
  ndwi_threshold?: number
  tile_size?: number
  stride?: number
  black_threshold?: number
  blur_threshold?: number
  sr_model_path?: string
  annotate_ships?: boolean
  ship_min_area_px?: number
  ship_max_area_px?: number
  ship_min_intensity?: number
  ship_threshold_percentile?: number
}

export type ExtractResponse = {
  job_id: string
  status: string
  total?: number
}

export type HealthResponse = {
  status: string
}

export type BackendJobRecord = {
  status?: string
  created_at?: string
  started_at?: string
  finished_at?: string
  location?: string
  date?: string
  error?: string
  result?: Record<string, unknown>
}

export type JobsResponse = Record<string, BackendJobRecord>

export type MetadataResponse = {
  path: string
  content: Record<string, unknown>
}

export type SummaryRow = Record<string, string>

export type SummaryResponse = {
  path: string
  content: SummaryRow[]
}
