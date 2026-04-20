import { useEffect, useMemo, useState, type FormEvent } from 'react'

import axios from 'axios'
import { motion } from 'framer-motion'
import {
  AlertCircle,
  CheckCircle2,
  LoaderCircle,
  MapPinned,
  Radar,
  Send,
  Waves,
} from 'lucide-react'

import { API_BASE_URL, createExtractionJob, fetchHealth, fetchJobStatus } from './api'
import { BboxMap } from './components/BboxMap'
import { PORT_PRESETS, type PortPreset } from './ports'
import type { BBox, ExtractionPayload, JobStatusResponse } from './types'
import './App.css'

const DEFAULT_PORT = PORT_PRESETS[0]

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.length > 0) {
      return detail
    }
    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unexpected error while contacting backend API.'
}

function formatBbox(bbox: BBox | null): string {
  if (!bbox) {
    return 'No bounding box selected'
  }

  return `minLon ${bbox[0].toFixed(4)}, minLat ${bbox[1].toFixed(4)}, maxLon ${bbox[2].toFixed(4)}, maxLat ${bbox[3].toFixed(4)}`
}

function formatPercent(value: number | undefined): string {
  if (value === undefined) {
    return '--'
  }

  return `${value.toFixed(2)}%`
}

function App() {
  const [apiHealth, setApiHealth] = useState<'checking' | 'online' | 'offline'>(
    'checking',
  )

  const [bbox, setBbox] = useState<BBox | null>([...DEFAULT_PORT.bbox] as BBox)
  const [locationName, setLocationName] = useState(DEFAULT_PORT.name)
  const [targetDate, setTargetDate] = useState(DEFAULT_PORT.date)
  const [projectId, setProjectId] = useState('fiery-surf-477011-p0')

  const [runFetch, setRunFetch] = useState(false)
  const [fetchOnly, setFetchOnly] = useState(false)
  const [skipVisualize, setSkipVisualize] = useState(true)

  const [driveFolder, setDriveFolder] = useState('GEE_Ship_Dataset')
  const [cloudFilterPct, setCloudFilterPct] = useState(10)
  const [ndwiThreshold, setNdwiThreshold] = useState(0)
  const [tileSize, setTileSize] = useState(256)
  const [stride, setStride] = useState(204)
  const [blackThreshold, setBlackThreshold] = useState(0.95)
  const [blurThreshold, setBlurThreshold] = useState(50)

  const [jobId, setJobId] = useState<string | null>(null)
  const [jobData, setJobData] = useState<JobStatusResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPolling, setIsPolling] = useState(false)
  const [lastPolledAt, setLastPolledAt] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    const checkHealth = async (): Promise<void> => {
      try {
        await fetchHealth()
        if (isMounted) {
          setApiHealth('online')
        }
      } catch {
        if (isMounted) {
          setApiHealth('offline')
        }
      }
    }

    void checkHealth()

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    if (!jobId || !isPolling) {
      return
    }

    let active = true

    const poll = async (): Promise<void> => {
      try {
        const nextStatus = await fetchJobStatus(jobId)
        if (!active) {
          return
        }

        setJobData(nextStatus)
        setLastPolledAt(new Date().toLocaleTimeString())

        if (nextStatus.status === 'complete' || nextStatus.status === 'failed') {
          setIsPolling(false)
        }
      } catch (error) {
        if (!active) {
          return
        }

        setErrorMessage(getErrorMessage(error))
        setIsPolling(false)
      }
    }

    void poll()

    const intervalId = window.setInterval(() => {
      void poll()
    }, 3000)

    return () => {
      active = false
      window.clearInterval(intervalId)
    }
  }, [jobId, isPolling])

  const statusLabel = (jobData?.status ?? (isSubmitting ? 'submitting' : 'idle')).toString()

  const statusClass = useMemo(() => {
    switch (statusLabel) {
      case 'queued':
        return 'queued'
      case 'running':
      case 'submitting':
        return 'running'
      case 'complete':
        return 'complete'
      case 'failed':
        return 'failed'
      default:
        return 'idle'
    }
  }, [statusLabel])

  const phase2 = jobData?.result?.phase2
  const phase3 = jobData?.result?.phase3
  const phase4 = jobData?.result?.phase4
  const phase6 = jobData?.result?.phase6

  const bboxFields = bbox ?? [0, 0, 0, 0]
  const canSubmit = bbox !== null && !isSubmitting

  const applyPreset = (preset: PortPreset): void => {
    setLocationName(preset.name)
    setTargetDate(preset.date)
    setBbox([...preset.bbox] as BBox)
  }

  const updateBboxValue = (index: number, value: string): void => {
    setBbox((current) => {
      const next: BBox = current ? ([...current] as BBox) : [0, 0, 0, 0]
      const parsed = Number(value)
      next[index] = Number.isFinite(parsed) ? parsed : 0
      return next
    })
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault()

    if (!bbox) {
      setErrorMessage('Draw or enter a valid bounding box before submitting.')
      return
    }

    setIsSubmitting(true)
    setErrorMessage(null)

    const payload: ExtractionPayload = {
      bbox,
      date: targetDate,
      location_name: locationName,
      project_id: projectId,
      run_fetch: runFetch,
      fetch_only: fetchOnly,
      skip_visualize: skipVisualize,
      drive_folder: driveFolder,
      cloud_filter_pct: cloudFilterPct,
      ndwi_threshold: ndwiThreshold,
      tile_size: tileSize,
      stride,
      black_threshold: blackThreshold,
      blur_threshold: blurThreshold,
    }

    try {
      const response = await createExtractionJob(payload)
      setJobId(response.job_id)
      setJobData({ status: response.status })
      setIsPolling(true)
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className='app-shell'>
      <motion.header
        className='hero-panel'
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.2, 0.9, 0.2, 1] }}
      >
        <p className='eyebrow'>
          <Radar size={16} />
          Harbor Atlas Console
        </p>
        <h1>Ship Dataset Control Deck</h1>
        <p className='hero-copy'>
          Draw your coastline ROI, dispatch an asynchronous extraction job, and track
          all six processing phases from masking to metadata generation.
        </p>
        <div className='hero-meta'>
          <span className={`health health-${apiHealth}`}>
            <Waves size={15} />
            API {apiHealth}
          </span>
          <span>
            <MapPinned size={15} />
            {formatBbox(bbox)}
          </span>
          <span className='mono'>Base URL: {API_BASE_URL}</span>
        </div>
      </motion.header>

      <main className='dashboard-grid'>
        <motion.section
          className='panel panel-control'
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.06, ease: [0.2, 0.9, 0.2, 1] }}
        >
          <h2>Mission Setup</h2>
          <p className='panel-subtitle'>
            Choose a preset or draw a custom rectangle on the map.
          </p>

          <div className='preset-row'>
            {PORT_PRESETS.map((preset) => (
              <button
                key={preset.name}
                type='button'
                className='preset-chip'
                onClick={() => applyPreset(preset)}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <form className='control-form' onSubmit={handleSubmit}>
            <div className='field-grid'>
              <label>
                Location Name
                <input
                  value={locationName}
                  onChange={(event) => setLocationName(event.target.value)}
                  placeholder='mumbai'
                  required
                />
              </label>

              <label>
                Target Date
                <input
                  type='date'
                  value={targetDate}
                  onChange={(event) => setTargetDate(event.target.value)}
                  required
                />
              </label>

              <label>
                GEE Project ID
                <input
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                  required
                />
              </label>

              <label>
                Drive Folder
                <input
                  value={driveFolder}
                  onChange={(event) => setDriveFolder(event.target.value)}
                  required
                />
              </label>
            </div>

            <div className='toggles'>
              <label>
                <input
                  type='checkbox'
                  checked={runFetch}
                  onChange={(event) => setRunFetch(event.target.checked)}
                />
                Run Phase 1 fetch (GEE export)
              </label>
              <label>
                <input
                  type='checkbox'
                  checked={fetchOnly}
                  onChange={(event) => setFetchOnly(event.target.checked)}
                />
                Fetch only (skip local phases)
              </label>
              <label>
                <input
                  type='checkbox'
                  checked={skipVisualize}
                  onChange={(event) => setSkipVisualize(event.target.checked)}
                />
                Skip matplotlib visualization
              </label>
            </div>

            <details className='advanced-panel'>
              <summary>Advanced processing controls</summary>
              <div className='advanced-grid'>
                <label>
                  Cloud Filter %
                  <input
                    type='number'
                    value={cloudFilterPct}
                    step='0.1'
                    min='0'
                    max='100'
                    onChange={(event) => setCloudFilterPct(Number(event.target.value))}
                  />
                </label>
                <label>
                  NDWI Threshold
                  <input
                    type='number'
                    value={ndwiThreshold}
                    step='0.01'
                    onChange={(event) => setNdwiThreshold(Number(event.target.value))}
                  />
                </label>
                <label>
                  Tile Size
                  <input
                    type='number'
                    value={tileSize}
                    min='64'
                    onChange={(event) => setTileSize(Number(event.target.value))}
                  />
                </label>
                <label>
                  Stride
                  <input
                    type='number'
                    value={stride}
                    min='32'
                    onChange={(event) => setStride(Number(event.target.value))}
                  />
                </label>
                <label>
                  Black Threshold
                  <input
                    type='number'
                    value={blackThreshold}
                    step='0.01'
                    min='0'
                    max='1'
                    onChange={(event) => setBlackThreshold(Number(event.target.value))}
                  />
                </label>
                <label>
                  Blur Threshold
                  <input
                    type='number'
                    value={blurThreshold}
                    step='1'
                    min='0'
                    onChange={(event) => setBlurThreshold(Number(event.target.value))}
                  />
                </label>
              </div>
            </details>

            <button className='submit-btn' type='submit' disabled={!canSubmit}>
              {isSubmitting ? <LoaderCircle className='spin' size={18} /> : <Send size={18} />}
              {isSubmitting ? 'Submitting...' : 'Start Extraction Job'}
            </button>
          </form>
        </motion.section>

        <motion.section
          className='panel panel-map'
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.14, ease: [0.2, 0.9, 0.2, 1] }}
        >
          <h2>ROI Map</h2>
          <p className='panel-subtitle'>
            Click one corner, then click the opposite corner to draw a rectangle.
            Right-click cancels an in-progress draw.
          </p>

          <BboxMap bbox={bbox} onBboxChange={setBbox} className='bbox-map' />

          <div className='map-actions'>
            <button type='button' className='clear-btn' onClick={() => setBbox(null)}>
              Clear BBox
            </button>
          </div>

          <div className='bbox-grid'>
            <label>
              Min Lon
              <input
                type='number'
                step='0.0001'
                value={bboxFields[0]}
                onChange={(event) => updateBboxValue(0, event.target.value)}
              />
            </label>
            <label>
              Min Lat
              <input
                type='number'
                step='0.0001'
                value={bboxFields[1]}
                onChange={(event) => updateBboxValue(1, event.target.value)}
              />
            </label>
            <label>
              Max Lon
              <input
                type='number'
                step='0.0001'
                value={bboxFields[2]}
                onChange={(event) => updateBboxValue(2, event.target.value)}
              />
            </label>
            <label>
              Max Lat
              <input
                type='number'
                step='0.0001'
                value={bboxFields[3]}
                onChange={(event) => updateBboxValue(3, event.target.value)}
              />
            </label>
          </div>

          <p className='bbox-readout'>{formatBbox(bbox)}</p>
        </motion.section>

        <motion.section
          className='panel panel-status'
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.22, ease: [0.2, 0.9, 0.2, 1] }}
        >
          <div className='status-head'>
            <h2>Job Tracker</h2>
            <span className={`status-pill ${statusClass}`}>{statusLabel}</span>
          </div>

          {errorMessage ? (
            <div className='error-banner'>
              <AlertCircle size={18} />
              {errorMessage}
            </div>
          ) : null}

          <div className='status-meta'>
            <span>Job ID: {jobId ?? 'not created yet'}</span>
            <span>Last refresh: {lastPolledAt ?? '--'}</span>
            <span>Polling: {isPolling ? 'active' : 'stopped'}</span>
          </div>

          {jobData?.status === 'complete' ? (
            <p className='success-note'>
              <CheckCircle2 size={18} />
              Extraction complete. Phase summaries are available below.
            </p>
          ) : null}

          <div className='phase-cards'>
            <article className='phase-card'>
              <h3>Phase 2 NDWI</h3>
              <p>Water Coverage</p>
              <strong>{formatPercent(phase2?.water_coverage_pct)}</strong>
            </article>

            <article className='phase-card'>
              <h3>Phase 3 Tiling</h3>
              <p>Saved / Rejected</p>
              <strong>
                {phase3?.tiles_saved ?? '--'} / {phase3?.tiles_rejected ?? '--'}
              </strong>
            </article>

            <article className='phase-card'>
              <h3>Phase 4 SR</h3>
              <p>Upscaled Tiles</p>
              <strong>{phase4?.tiles_upscaled ?? '--'}</strong>
            </article>

            <article className='phase-card'>
              <h3>Phase 6 Dataset</h3>
              <p>Total Tiles</p>
              <strong>{phase6?.total_tiles ?? '--'}</strong>
            </article>
          </div>

          {jobData?.result ? (
            <details className='json-dump'>
              <summary>Raw run summary JSON</summary>
              <pre>{JSON.stringify(jobData.result, null, 2)}</pre>
            </details>
          ) : null}
        </motion.section>
      </main>
    </div>
  )
}

export default App
