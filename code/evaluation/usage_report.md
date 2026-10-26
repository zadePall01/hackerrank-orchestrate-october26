# Final full-dataset run usage

Run requests: 518. Elapsed seconds: 1.635.
Final output published: False. Output SHA-256: not produced.
Dataset fingerprint: `b5863ab0d24ea781de41b22f487ce4470579abd3e0b01ed7de1736a06251d863`.

| Provider / model | Calls | Input tokens | Output tokens | Total tokens | Tokens/request | Estimated cost USD | Cost/request USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| No generative model used | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Overall generative inference | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

PDF extraction uses pypdf. Local OCR uses the RapidOCR package's bundled
PP-OCRv6 detection/recognition and mobile orientation models through ONNX Runtime.
These are local non-generative models: token counts do not apply. Actual local
OCR invocations in this run: 0. Each invokes bundled detection,
orientation, and recognition networks; recognition batches vary with image text.
Document extraction cache hits: 15. These are not hosted model API
calls. No credentials, inference service, or runtime network access is
used. Local compute and electricity costs are not measured and are not included
in the zero hosted-inference cost. Development-assistant usage is separate from
the submitted pipeline run and is not represented as pipeline inference.

An unpublished output means this run did not satisfy the submission contract;
see diagnostics rather than interpreting failure as a successful full run.
