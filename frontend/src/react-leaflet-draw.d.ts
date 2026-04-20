declare module 'react-leaflet-draw' {
  import * as React from 'react'
  import type L from 'leaflet'

  export interface EditControlProps {
    position?: 'topright' | 'topleft' | 'bottomright' | 'bottomleft'
    onEdited?: (event: L.DrawEvents.Edited) => void
    onCreated?: (event: L.DrawEvents.Created) => void
    onDeleted?: (event: L.DrawEvents.Deleted) => void
    draw?: unknown
    edit?: unknown
  }

  export class EditControl extends React.Component<EditControlProps> {}
}
