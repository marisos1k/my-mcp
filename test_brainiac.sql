--
-- PostgreSQL database dump
--

\restrict D5wrOSO84HXLuA3sM21Bdc420RGIwU7wTzNyDOp2A9tC7CO2eJPq2LcWdUrjR4Z

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

-- Started on 2026-04-30 14:20:14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 233 (class 1259 OID 17091)
-- Name: api_keys; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.api_keys (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    key_name character varying(100) NOT NULL,
    key_hash character varying(255) NOT NULL,
    key_salt character varying(255) NOT NULL,
    key_prefix character varying(10) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_used_at timestamp without time zone,
    is_active boolean DEFAULT true
);


ALTER TABLE public.api_keys OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 17111)
-- Name: api_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.api_keys_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.api_keys_id_seq OWNER TO postgres;

--
-- TOC entry 5023 (class 0 OID 0)
-- Dependencies: 234
-- Name: api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.api_keys_id_seq OWNED BY public.api_keys.id;


--
-- TOC entry 219 (class 1259 OID 16904)
-- Name: links; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.links (
    id bigint NOT NULL,
    from_node bigint NOT NULL,
    to_node bigint NOT NULL,
    CONSTRAINT links_check CHECK ((from_node <> to_node))
);


ALTER TABLE public.links OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 16911)
-- Name: links_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.links_id_seq OWNER TO postgres;

--
-- TOC entry 5024 (class 0 OID 0)
-- Dependencies: 220
-- Name: links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.links_id_seq OWNED BY public.links.id;


--
-- TOC entry 221 (class 1259 OID 16912)
-- Name: node_types; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.node_types (
    id bigint NOT NULL,
    tool_id bigint NOT NULL,
    name character varying(150) NOT NULL,
    description text
);


ALTER TABLE public.node_types OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 16920)
-- Name: node_types_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.node_types_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.node_types_id_seq OWNER TO postgres;

--
-- TOC entry 5025 (class 0 OID 0)
-- Dependencies: 222
-- Name: node_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.node_types_id_seq OWNED BY public.node_types.id;


--
-- TOC entry 223 (class 1259 OID 16921)
-- Name: nodes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.nodes (
    id bigint NOT NULL,
    pipeline_id bigint NOT NULL,
    type_id bigint NOT NULL,
    nested_pipeline_id bigint,
    attempts integer DEFAULT 0 NOT NULL,
    report text,
    coords point,
    CONSTRAINT nodes_attempts_check CHECK ((attempts >= 0))
);


ALTER TABLE public.nodes OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16932)
-- Name: nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.nodes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.nodes_id_seq OWNER TO postgres;

--
-- TOC entry 5026 (class 0 OID 0)
-- Dependencies: 224
-- Name: nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.nodes_id_seq OWNED BY public.nodes.id;


--
-- TOC entry 225 (class 1259 OID 16933)
-- Name: pipelines; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pipelines (
    id bigint NOT NULL,
    project_id bigint NOT NULL,
    name character varying(200) NOT NULL,
    max_time interval,
    max_cost numeric(12,2),
    max_fail_percent numeric(5,2),
    score numeric(5,2),
    report text,
    CONSTRAINT pipelines_max_cost_check CHECK (((max_cost IS NULL) OR (max_cost >= (0)::numeric))),
    CONSTRAINT pipelines_max_fail_percent_check CHECK (((max_fail_percent IS NULL) OR ((max_fail_percent >= (0)::numeric) AND (max_fail_percent <= (100)::numeric)))),
    CONSTRAINT pipelines_score_check CHECK (((score IS NULL) OR ((score >= (0)::numeric) AND (score <= (10)::numeric))))
);


ALTER TABLE public.pipelines OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16944)
-- Name: pipelines_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.pipelines_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pipelines_id_seq OWNER TO postgres;

--
-- TOC entry 5027 (class 0 OID 0)
-- Dependencies: 226
-- Name: pipelines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.pipelines_id_seq OWNED BY public.pipelines.id;


--
-- TOC entry 227 (class 1259 OID 16945)
-- Name: projects; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.projects (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    name character varying(200) NOT NULL
);


ALTER TABLE public.projects OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 16951)
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.projects_id_seq OWNER TO postgres;

--
-- TOC entry 5028 (class 0 OID 0)
-- Dependencies: 228
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- TOC entry 229 (class 1259 OID 16952)
-- Name: tools; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tools (
    id bigint NOT NULL,
    name character varying(150) NOT NULL,
    config jsonb
);


ALTER TABLE public.tools OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 16959)
-- Name: tools_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tools_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tools_id_seq OWNER TO postgres;

--
-- TOC entry 5029 (class 0 OID 0)
-- Dependencies: 230
-- Name: tools_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tools_id_seq OWNED BY public.tools.id;


--
-- TOC entry 231 (class 1259 OID 16960)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    email character varying(255) NOT NULL,
    pass_hash text DEFAULT ''::text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 16968)
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- TOC entry 5030 (class 0 OID 0)
-- Dependencies: 232
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- TOC entry 4800 (class 2604 OID 17112)
-- Name: api_keys id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_keys ALTER COLUMN id SET DEFAULT nextval('public.api_keys_id_seq'::regclass);


--
-- TOC entry 4790 (class 2604 OID 16970)
-- Name: links id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.links ALTER COLUMN id SET DEFAULT nextval('public.links_id_seq'::regclass);


--
-- TOC entry 4791 (class 2604 OID 16971)
-- Name: node_types id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.node_types ALTER COLUMN id SET DEFAULT nextval('public.node_types_id_seq'::regclass);


--
-- TOC entry 4792 (class 2604 OID 16972)
-- Name: nodes id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nodes ALTER COLUMN id SET DEFAULT nextval('public.nodes_id_seq'::regclass);


--
-- TOC entry 4794 (class 2604 OID 16973)
-- Name: pipelines id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pipelines ALTER COLUMN id SET DEFAULT nextval('public.pipelines_id_seq'::regclass);


--
-- TOC entry 4795 (class 2604 OID 16974)
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- TOC entry 4796 (class 2604 OID 16975)
-- Name: tools id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tools ALTER COLUMN id SET DEFAULT nextval('public.tools_id_seq'::regclass);


--
-- TOC entry 4797 (class 2604 OID 16976)
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- TOC entry 5016 (class 0 OID 17091)
-- Dependencies: 233
-- Data for Name: api_keys; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.api_keys (id, user_id, key_name, key_hash, key_salt, key_prefix, created_at, last_used_at, is_active) FROM stdin;
2	1	test_api_key	b445078a26a9fc244fc5cdc80d2e54cb26fd49ce0470de6a30b6061acf9b6c8022e6d5c02a59c733d5698a354b9db955fb3d09268fcd384aaa5221a86288a16a	bc0278efa099cdd8b33a7288bfde0189cd2b0ece2060dadcd36bf1f98b85d92e	tm_E8ZCwJp	2026-04-30 05:34:08.797043	2026-04-30 05:36:44.382066	t
1	1	schedule	bfdcd024f2fc8181352bfc7ca64860efe006fa0face56b651b1d22812d3a03442d89a972da1b6df93d8d8b604900ea0e12483a29e7818fd937f46b988fe1c96e	47814892c94c78b070ef6226c32fe7a13703fc49d059f81b10abdaccf2e2d964	tm_iFp4poC	2026-04-30 05:26:12.155735	2026-04-30 12:43:40.487931	t
\.


--
-- TOC entry 5002 (class 0 OID 16904)
-- Dependencies: 219
-- Data for Name: links; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.links (id, from_node, to_node) FROM stdin;
1	1	2
2	2	3
3	3	4
\.


--
-- TOC entry 5004 (class 0 OID 16912)
-- Dependencies: 221
-- Data for Name: node_types; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.node_types (id, tool_id, name, description) FROM stdin;
1	1	parse_request	Парсинг запроса
2	2	check_availability	Проверка календаря
3	3	find_best_time	Поиск времени
4	4	send_notification	Уведомление
\.


--
-- TOC entry 5006 (class 0 OID 16921)
-- Dependencies: 223
-- Data for Name: nodes; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.nodes (id, pipeline_id, type_id, nested_pipeline_id, attempts, report, coords) FROM stdin;
1	1	1	\N	0	\N	(100,100)
2	1	2	\N	0	\N	(100,200)
3	1	3	\N	0	\N	(300,200)
4	1	4	\N	0	\N	(500,200)
\.


--
-- TOC entry 5008 (class 0 OID 16933)
-- Dependencies: 225
-- Data for Name: pipelines; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.pipelines (id, project_id, name, max_time, max_cost, max_fail_percent, score, report) FROM stdin;
1	1	schedule_agent	01:00:00	10.00	5.00	8.50	ИИ агент для управления расписанием
\.


--
-- TOC entry 5010 (class 0 OID 16945)
-- Dependencies: 227
-- Data for Name: projects; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.projects (id, user_id, name) FROM stdin;
1	1	time_manager
\.


--
-- TOC entry 5012 (class 0 OID 16952)
-- Dependencies: 229
-- Data for Name: tools; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tools (id, name, config) FROM stdin;
1	llm	{"model": "local"}
2	calendar_api	{}
3	scheduler	{}
4	notifier	{}
\.


--
-- TOC entry 5014 (class 0 OID 16960)
-- Dependencies: 231
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, email, pass_hash, created_at) FROM stdin;
1	test_user@example.com	hash_for_test123	2026-04-30 02:48:57.57399
\.


--
-- TOC entry 5031 (class 0 OID 0)
-- Dependencies: 234
-- Name: api_keys_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.api_keys_id_seq', 2, true);


--
-- TOC entry 5032 (class 0 OID 0)
-- Dependencies: 220
-- Name: links_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.links_id_seq', 3, true);


--
-- TOC entry 5033 (class 0 OID 0)
-- Dependencies: 222
-- Name: node_types_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.node_types_id_seq', 4, true);


--
-- TOC entry 5034 (class 0 OID 0)
-- Dependencies: 224
-- Name: nodes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.nodes_id_seq', 4, true);


--
-- TOC entry 5035 (class 0 OID 0)
-- Dependencies: 226
-- Name: pipelines_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.pipelines_id_seq', 1, true);


--
-- TOC entry 5036 (class 0 OID 0)
-- Dependencies: 228
-- Name: projects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.projects_id_seq', 1, true);


--
-- TOC entry 5037 (class 0 OID 0)
-- Dependencies: 230
-- Name: tools_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tools_id_seq', 4, true);


--
-- TOC entry 5038 (class 0 OID 0)
-- Dependencies: 232
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 1, true);


--
-- TOC entry 4842 (class 2606 OID 17105)
-- Name: api_keys api_keys_key_hash_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_key_hash_key UNIQUE (key_hash);


--
-- TOC entry 4811 (class 2606 OID 16980)
-- Name: links links_from_node_to_node_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.links
    ADD CONSTRAINT links_from_node_to_node_key UNIQUE (from_node, to_node);


--
-- TOC entry 4813 (class 2606 OID 16982)
-- Name: links links_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.links
    ADD CONSTRAINT links_pkey PRIMARY KEY (id);


--
-- TOC entry 4815 (class 2606 OID 16984)
-- Name: node_types node_types_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.node_types
    ADD CONSTRAINT node_types_pkey PRIMARY KEY (id);


--
-- TOC entry 4817 (class 2606 OID 16986)
-- Name: node_types node_types_tool_id_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.node_types
    ADD CONSTRAINT node_types_tool_id_name_key UNIQUE (tool_id, name);


--
-- TOC entry 4822 (class 2606 OID 16988)
-- Name: nodes nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT nodes_pkey PRIMARY KEY (id);


--
-- TOC entry 4825 (class 2606 OID 16990)
-- Name: pipelines pipelines_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pipelines
    ADD CONSTRAINT pipelines_pkey PRIMARY KEY (id);


--
-- TOC entry 4827 (class 2606 OID 16992)
-- Name: pipelines pipelines_project_id_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pipelines
    ADD CONSTRAINT pipelines_project_id_name_key UNIQUE (project_id, name);


--
-- TOC entry 4830 (class 2606 OID 16994)
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- TOC entry 4832 (class 2606 OID 16996)
-- Name: projects projects_user_id_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_user_id_name_key UNIQUE (user_id, name);


--
-- TOC entry 4834 (class 2606 OID 16998)
-- Name: tools tools_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_name_key UNIQUE (name);


--
-- TOC entry 4836 (class 2606 OID 17000)
-- Name: tools tools_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_pkey PRIMARY KEY (id);


--
-- TOC entry 4838 (class 2606 OID 17002)
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- TOC entry 4840 (class 2606 OID 17004)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 4843 (class 1259 OID 17115)
-- Name: idx_api_keys_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_keys_active ON public.api_keys USING btree (is_active);


--
-- TOC entry 4844 (class 1259 OID 17114)
-- Name: idx_api_keys_prefix; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_keys_prefix ON public.api_keys USING btree (key_prefix);


--
-- TOC entry 4845 (class 1259 OID 17113)
-- Name: idx_api_keys_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_api_keys_user_id ON public.api_keys USING btree (user_id);


--
-- TOC entry 4808 (class 1259 OID 17006)
-- Name: idx_links_from_node; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_links_from_node ON public.links USING btree (from_node);


--
-- TOC entry 4809 (class 1259 OID 17007)
-- Name: idx_links_to_node; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_links_to_node ON public.links USING btree (to_node);


--
-- TOC entry 4818 (class 1259 OID 17008)
-- Name: idx_nodes_nested_pipeline_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_nodes_nested_pipeline_id ON public.nodes USING btree (nested_pipeline_id);


--
-- TOC entry 4819 (class 1259 OID 17009)
-- Name: idx_nodes_pipeline_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_nodes_pipeline_id ON public.nodes USING btree (pipeline_id);


--
-- TOC entry 4820 (class 1259 OID 17010)
-- Name: idx_nodes_type_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_nodes_type_id ON public.nodes USING btree (type_id);


--
-- TOC entry 4823 (class 1259 OID 17011)
-- Name: idx_pipelines_project_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_pipelines_project_id ON public.pipelines USING btree (project_id);


--
-- TOC entry 4828 (class 1259 OID 17012)
-- Name: idx_projects_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_projects_user_id ON public.projects USING btree (user_id);


--
-- TOC entry 4854 (class 2606 OID 17106)
-- Name: api_keys api_keys_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4846 (class 2606 OID 17018)
-- Name: links links_from_node_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.links
    ADD CONSTRAINT links_from_node_fkey FOREIGN KEY (from_node) REFERENCES public.nodes(id) ON DELETE CASCADE;


--
-- TOC entry 4847 (class 2606 OID 17023)
-- Name: links links_to_node_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.links
    ADD CONSTRAINT links_to_node_fkey FOREIGN KEY (to_node) REFERENCES public.nodes(id) ON DELETE CASCADE;


--
-- TOC entry 4848 (class 2606 OID 17028)
-- Name: node_types node_types_tool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.node_types
    ADD CONSTRAINT node_types_tool_id_fkey FOREIGN KEY (tool_id) REFERENCES public.tools(id) ON DELETE RESTRICT;


--
-- TOC entry 4849 (class 2606 OID 17033)
-- Name: nodes nodes_nested_pipeline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT nodes_nested_pipeline_id_fkey FOREIGN KEY (nested_pipeline_id) REFERENCES public.pipelines(id) ON DELETE SET NULL;


--
-- TOC entry 4850 (class 2606 OID 17038)
-- Name: nodes nodes_pipeline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT nodes_pipeline_id_fkey FOREIGN KEY (pipeline_id) REFERENCES public.pipelines(id) ON DELETE CASCADE;


--
-- TOC entry 4851 (class 2606 OID 17043)
-- Name: nodes nodes_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT nodes_type_id_fkey FOREIGN KEY (type_id) REFERENCES public.node_types(id) ON DELETE RESTRICT;


--
-- TOC entry 4852 (class 2606 OID 17048)
-- Name: pipelines pipelines_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pipelines
    ADD CONSTRAINT pipelines_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- TOC entry 4853 (class 2606 OID 17053)
-- Name: projects projects_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


-- Completed on 2026-04-30 14:20:14

--
-- PostgreSQL database dump complete
--

\unrestrict D5wrOSO84HXLuA3sM21Bdc420RGIwU7wTzNyDOp2A9tC7CO2eJPq2LcWdUrjR4Z

