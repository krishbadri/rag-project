'use client'

import React, { useState, useCallback } from 'react'
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react'

interface UploadStatus {
  id: string
  filename: string
  status: 'uploading' | 'processing' | 'completed' | 'error'
  progress: number
  error?: string
  documentId?: string
}

export default function FileUpload() {
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploads, setUploads] = useState<UploadStatus[]>([])
  const [startNewBatch, setStartNewBatch] = useState(false)
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null)

  React.useEffect(() => {
    try {
      const id = typeof window !== 'undefined' ? localStorage.getItem('current_batch_id') : null
      if (id) setCurrentBatchId(id)
    } catch {}
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback(async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
    
    const files = Array.from(e.dataTransfer.files) as File[]
    await uploadFiles(files)
  }, [])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []) as File[]
    await uploadFiles(files)
  }, [])

  const uploadFiles = async (files: File[]) => {
    // Decide batch ID: reuse existing unless user opts to start new
    let batchId = ''
    try {
      const existing = typeof window !== 'undefined' ? localStorage.getItem('current_batch_id') : null
      if (existing && !startNewBatch) {
        batchId = existing
      } else {
        const resp = await fetch('/api/uploads/batches', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        })
        if (resp.ok) {
          const data = await resp.json()
          batchId = data.id
        } else {
          batchId = Math.random().toString(36).slice(2)
        }
        if (typeof window !== 'undefined') {
          localStorage.setItem('current_batch_id', batchId)
          localStorage.setItem('current_batch_document_ids', JSON.stringify([]))
          localStorage.setItem('recent_document_ids', JSON.stringify([]))
        }
      }
      setCurrentBatchId(batchId)
    } catch {
      // Fallback
      batchId = Math.random().toString(36).slice(2)
      if (typeof window !== 'undefined') {
        localStorage.setItem('current_batch_id', batchId)
      }
      setCurrentBatchId(batchId)
    }
    for (const file of files) {
      const uploadId = Math.random().toString(36).substr(2, 9)
      
      // Add to uploads list
      setUploads((prev: UploadStatus[]) => [...prev, {
        id: uploadId,
        filename: file.name,
        status: 'uploading',
        progress: 0
      }])

      try {
        // Step 1: Initialize upload
        const initResponse = await fetch('/api/uploads/init', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            filename: file.name,
            mime_type: file.type,
            size_bytes: file.size,
            batch_id: batchId,
          })
        })

        if (!initResponse.ok) {
          throw new Error('Failed to initialize upload')
        }

        const { document_id, upload_url, fields } = await initResponse.json()

        // Step 2: Upload to storage (direct backend or S3/MinIO)
        if ((fields as any)?.direct === 'true') {
          const formData = new FormData()
          formData.append('document_id', document_id)
          formData.append('file', file)

          const directResponse = await fetch(upload_url, {
            method: 'POST',
            body: formData,
          })
          if (!directResponse.ok) {
            throw new Error('Failed to upload file (direct)')
          }
        } else if ((fields as any)?.mock === 'true') {
          const mockResponse = await fetch(upload_url, { method: 'POST' })
          if (!mockResponse.ok) {
            throw new Error('Failed to upload file (mock)')
          }
        } else {
          const formData = new FormData()
          Object.entries(fields).forEach(([key, value]) => {
            formData.append(key, value as string)
          })
          formData.append('file', file)

          const uploadResponse = await fetch(upload_url, {
            method: 'POST',
            body: formData
          })

          if (!uploadResponse.ok) {
            throw new Error('Failed to upload file')
          }
        }

        // Step 3: Complete upload
        await fetch(`/api/uploads/${document_id}/complete`, {
          method: 'POST'
        })

        // Update status
        setUploads((prev: UploadStatus[]) => prev.map((upload: UploadStatus) =>
          upload.id === uploadId
            ? { ...upload, status: 'processing', progress: 100, documentId: document_id }
            : upload
        ))

        // Record current batch document IDs locally for scoping chat retrieval
        try {
          const keyNew = 'current_batch_document_ids'
          const existingRawNew = typeof window !== 'undefined' ? localStorage.getItem(keyNew) : null
          const existingNew: string[] = existingRawNew ? JSON.parse(existingRawNew) : []
          const nextNew = Array.from(new Set([...existingNew, document_id]))
          localStorage.setItem(keyNew, JSON.stringify(nextNew))

          // Maintain the older key for compatibility with older chat components
          const keyOld = 'recent_document_ids'
          const existingRawOld = typeof window !== 'undefined' ? localStorage.getItem(keyOld) : null
          const existingOld: string[] = existingRawOld ? JSON.parse(existingRawOld) : []
          const nextOld = Array.from(new Set([...existingOld, document_id]))
          localStorage.setItem(keyOld, JSON.stringify(nextOld))
        } catch (e) {
          // non-fatal
          console.warn('Could not persist recent document id', e)
        }

        // TODO: Poll for job completion
        // For now, mark as completed after a delay
        setTimeout(() => {
          setUploads((prev: UploadStatus[]) => prev.map((upload: UploadStatus) => 
            upload.id === uploadId 
              ? { ...upload, status: 'completed' }
              : upload
          ))
        }, 3000)

        } catch (error) {
        console.error('Upload error:', error)
        setUploads((prev: UploadStatus[]) => prev.map((upload: UploadStatus) => 
          upload.id === uploadId 
            ? { ...upload, status: 'error', error: error instanceof Error ? error.message : 'Upload failed' }
            : upload
        ))
      }
    }
  }

  const removeUpload = (id: string) => {
    setUploads((prev: UploadStatus[]) => prev.filter((upload: UploadStatus) => upload.id !== id))
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Upload Documents
        </h2>
        <p className="text-gray-600">
          Upload PDFs, images, or videos to ask questions about them
        </p>
      </div>

      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          isDragOver
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        <p className="text-lg font-medium text-gray-900 mb-2">
          Drop files here or click to browse
        </p>
        <p className="text-sm text-gray-500 mb-4">
          Supports PDF, PNG, JPG, MP4 files up to 100MB
        </p>
        <div className="flex items-center justify-center space-x-3 mb-3 text-sm text-gray-700">
          <label className="flex items-center space-x-2">
            <input type="checkbox" checked={startNewBatch} onChange={(e) => setStartNewBatch(e.target.checked)} />
            <span>Start a new batch for this selection</span>
          </label>
          <span className="text-gray-400">•</span>
          <span>Current batch: {currentBatchId ? currentBatchId.slice(0,6) : 'none'}</span>
        </div>
        <input
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.mp4"
          onChange={handleFileSelect}
          className="hidden"
          id="file-upload"
        />
        <label
          htmlFor="file-upload"
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
        >
          Choose Files
        </label>
      </div>

      {/* Upload Status */}
      {uploads.length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Upload Status</h3>
          <div className="space-y-3">
            {uploads.map((upload: UploadStatus) => (
              <div
                key={upload.id}
                className="flex items-center justify-between p-4 bg-white rounded-lg border"
              >
                <div className="flex items-center space-x-3">
                  <File className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {upload.filename}
                    </p>
                    <p className="text-xs text-gray-500">
                      {upload.status === 'uploading' && 'Uploading...'}
                      {upload.status === 'processing' && 'Processing...'}
                      {upload.status === 'completed' && 'Completed'}
                      {upload.status === 'error' && upload.error}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {upload.status === 'uploading' && (
                    <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  )}
                  {upload.status === 'processing' && (
                    <div className="w-4 h-4 border-2 border-yellow-600 border-t-transparent rounded-full animate-spin" />
                  )}
                  {upload.status === 'completed' && (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  )}
                  {upload.status === 'error' && (
                    <AlertCircle className="h-5 w-5 text-red-500" />
                  )}
                  <button
                    onClick={() => removeUpload(upload.id)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
