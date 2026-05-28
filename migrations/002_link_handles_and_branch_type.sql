-- Порты на рёбрах + тип узла «ветвление» (да / нет / ошибка)
-- psql -U postgres -d test_brainiac -f migrations/002_link_handles_and_branch_type.sql

ALTER TABLE public.links
    ADD COLUMN IF NOT EXISTS source_handle character varying(50) DEFAULT 'out',
    ADD COLUMN IF NOT EXISTS target_handle character varying(50) DEFAULT 'in';

UPDATE public.tools
SET config = COALESCE(config, '{}'::jsonb) || '{"react_component":"workflow","color":"#3d5afe","inputs":[{"id":"in","label":"In"}],"outputs":[{"id":"out","label":"Out"}]}'::jsonb
WHERE name IN ('llm', 'calendar_api', 'scheduler', 'notifier')
  AND (config IS NULL OR config = '{}'::jsonb OR NOT (config ? 'react_component'));

INSERT INTO public.tools (name, config)
SELECT
    'branch_router',
    '{
      "react_component": "branch",
      "color": "#7c4dff",
      "inputs": [{"id": "in", "label": "In"}],
      "outputs": [
        {"id": "yes", "label": "Да"},
        {"id": "no", "label": "Нет"},
        {"id": "error", "label": "Ошибка"}
      ]
    }'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM public.tools WHERE name = 'branch_router');

INSERT INTO public.node_types (tool_id, name, description)
SELECT t.id, 'branch', 'Ветвление: да / нет / ошибка'
FROM public.tools t
WHERE t.name = 'branch_router'
  AND NOT EXISTS (
      SELECT 1 FROM public.node_types nt
      WHERE nt.name = 'branch' AND nt.tool_id = t.id
  );
