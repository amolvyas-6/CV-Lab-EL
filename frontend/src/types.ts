export type BBox = [number, number, number, number]

export interface ExtractionPayload {
  bbox: BBox
  date: string
  location_name: string
  project_id?: string
  run_fetch?: boolean
  fetch_only?: boolean
  skip_visualize?: boolean
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
}

export interface ExtractionResponse {
  job_id: string
  status: string
}

export interface Phase2Summary {
  water_coverage_pct: number
}

export interface Phase3Summary {
  total_windows: number
  tiles_saved: number
  tiles_rejected: number
  write_failures: number
}

export interface Phase4Summary {
  tiles_found: number
  tiles_upscaled: number
  skipped_unreadable: number
  failed_sr: number
  failed_write: number
  skipped?: boolean
  reason?: string
}

export interface Phase6Summary {
  metadata_path: string
  summary_csv_path: string
  total_tiles: number
  total_tiles_sr: number
  locations_count: number
}

export interface PipelineRunResult {
  phase1?: { task_id?: string; skipped?: boolean; reason?: string }
  phase2?: Phase2Summary
  phase3?: Phase3Summary
  phase4?: Phase4Summary
  phase6?: Phase6Summary
}

export interface JobStatusResponse {
  status: string
  created_at?: string
  started_at?: string
  finished_at?: string
  location?: string
  date?: string
  error?: string
  result?: PipelineRunResult
}
