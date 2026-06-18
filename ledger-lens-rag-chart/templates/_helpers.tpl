{{/*
Expand the name of the chart.
*/}}
{{- define "ledger-lens-rag-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ledger-lens-rag-chart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ledger-lens-rag-chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ledger-lens-rag-chart.labels" -}}
helm.sh/chart: {{ include "ledger-lens-rag-chart.chart" . }}
{{ include "ledger-lens-rag-chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ledger-lens-rag-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ledger-lens-rag-chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ledger-lens-rag-chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ledger-lens-rag-chart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the Secret holding provider API keys, either user-supplied or chart-managed.
*/}}
{{- define "ledger-lens-rag-chart.secretName" -}}
{{- default (printf "%s-secret" (include "ledger-lens-rag-chart.fullname" .)) .Values.secretEnv.existingSecret }}
{{- end }}

{{/*
Name of the PVC backing the FAISS index, either user-supplied or chart-managed.
*/}}
{{- define "ledger-lens-rag-chart.pvcName" -}}
{{- default (printf "%s-data" (include "ledger-lens-rag-chart.fullname" .)) .Values.persistence.existingClaim }}
{{- end }}
