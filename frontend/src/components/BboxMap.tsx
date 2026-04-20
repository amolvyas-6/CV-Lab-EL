import { useEffect, useMemo, useRef } from 'react'

import L, { type LatLngBoundsExpression, type LatLngTuple } from 'leaflet'
import {
  MapContainer,
  Rectangle,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'

import type { BBox } from '../types'

interface BboxMapProps {
  bbox: BBox | null
  onBboxChange: (bbox: BBox | null) => void
  className?: string
}

function bboxToBounds(bbox: BBox): LatLngBoundsExpression {
  return [
    [bbox[1], bbox[0]],
    [bbox[3], bbox[2]],
  ]
}

function boundsToBbox(bounds: L.LatLngBounds): BBox {
  const southWest = bounds.getSouthWest()
  const northEast = bounds.getNorthEast()
  return [southWest.lng, southWest.lat, northEast.lng, northEast.lat]
}

function DrawRectangleWithClicks({
  onBboxChange,
}: {
  onBboxChange: (bbox: BBox) => void
}): null {
  const anchorRef = useRef<L.LatLng | null>(null)

  useMapEvents({
    click(event) {
      if (!anchorRef.current) {
        anchorRef.current = event.latlng
        return
      }

      const bounds = L.latLngBounds(anchorRef.current, event.latlng)
      onBboxChange(boundsToBbox(bounds))
      anchorRef.current = null
    },
    contextmenu() {
      anchorRef.current = null
    },
  })

  return null
}

function FitSelectedBounds({
  bounds,
}: {
  bounds: LatLngBoundsExpression | null
}): null {
  const map = useMap()

  useEffect(() => {
    if (!bounds) {
      return
    }

    map.fitBounds(bounds, {
      padding: [28, 28],
      maxZoom: 13,
    })
  }, [map, bounds])

  return null
}

export function BboxMap({ bbox, onBboxChange, className }: BboxMapProps) {
  const bounds = useMemo(() => {
    if (!bbox) {
      return null
    }

    return bboxToBounds(bbox)
  }, [bbox])

  const center = useMemo<LatLngTuple>(() => {
    if (!bbox) {
      return [19.076, 72.877]
    }

    return [(bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2]
  }, [bbox])

  return (
    <MapContainer
      center={center}
      zoom={11}
      scrollWheelZoom
      className={className ?? 'bbox-map'}
    >
      <FitSelectedBounds bounds={bounds} />
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      />
      <DrawRectangleWithClicks
        onBboxChange={(nextBbox) => {
          onBboxChange(nextBbox)
        }}
      />
      {bounds ? (
        <Rectangle
          bounds={bounds}
          pathOptions={{
            color: '#ef7d43',
            weight: 2,
            fillOpacity: 0.12,
          }}
        />
      ) : null}
    </MapContainer>
  )
}
