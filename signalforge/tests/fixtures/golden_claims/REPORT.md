### GC-01 · historical_prose_standalone_vs_consolidated · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 44 claims |
| expected[59413] | ok | status in ['extracted'], MW As on 31 March 2025 | extracted |
| expected[79930] | ok | status in ['ambiguous', 'needs_review'], MW As on 31 March 2025 | ambiguous |

### GC-02 · historical_prose_with_national_comparator · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 44 claims |
| forbidden_extracted[69.96] | ok | never `extracted` | [('needs_review', None)] |
| expected[77.44] | ok | status in ['extracted'], percent FY25 | extracted |

### GC-03 · group_level_flow_relative_period · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 44 claims |
| expected[3972] | ok | status in ['ambiguous', 'needs_review'], MW None | ambiguous |

### GC-04 · multiple_numbers_growth_percent · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 44 claims |
| forbidden_extracted[29] | ok | never `extracted` | [('needs_review', None)] |
| expected[35.64] | ok | status in ['extracted', 'ambiguous', 'needs_review'], MMT FY24 | extracted |
| expected[45.82] | ok | status in ['extracted', 'ambiguous', 'needs_review'], MMT FY25 | extracted |

### GC-05 · multiple_numbers_group_level_coal_received · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 44 claims |
| forbidden_extracted[282.8] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[5.2] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[268.7] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[2.53] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[10.5] | ok | never `extracted` | [('needs_review', None)] |

### GC-06 · forward_looking_target · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 30 claims |
| forbidden_extracted[60] | ok | never `extracted` | [('needs_review', 'capacity_target')] |
| expected[60] | ok | status in ['ambiguous', 'needs_review'], GW None | needs_review |

### GC-07 · forward_looking_plan_and_target · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 27 claims |
| forbidden_extracted[130] | ok | never `extracted` | [('ambiguous', 'capacity_target')] |
| forbidden_extracted[60] | ok | never `extracted` | [('needs_review', None)] |

### GC-08 · national_figure · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 61 claims |
| forbidden_extracted[172] | ok | never `extracted` | [('ambiguous', 'capacity')] |
| forbidden_extracted[33242] | ok | never `extracted` | [('ambiguous', 'capacity_addition')] |

### GC-09 · subsidiary_neepco · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 28 claims |
| forbidden_extracted[2057] | ok | never `extracted` | [('needs_review', 'installed_capacity')] |
| forbidden_extracted[8020] | ok | never `extracted` | [('needs_review', 'plant_load_factor')] |
| forbidden_extracted[1000] | ok | never `extracted` | [('needs_review', 'capacity')] |
| expected[250] | ok | status in ['ambiguous', 'needs_review'], INR crore FY 2024-25 | needs_review |

### GC-10 · joint_venture_acquisition · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 44 claims |
| forbidden_extracted[2123] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[1989.7] | ok | never `extracted` | [('needs_review', 'capacity_under_construction')] |
| forbidden_extracted[19500] | ok | never `extracted` | [('needs_review', None)] |

### GC-11 · under_implementation_including_jv · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 30 claims |
| forbidden_extracted[18295] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[16900] | ok | never `extracted` | [('needs_review', 'commercial_capacity')] |
| forbidden_extracted[14516] | ok | never `extracted` | not emitted |
| expected[33671] | ok | status in ['ambiguous', 'needs_review'], MW As on 31 March 2025 | ambiguous |

### GC-12 · unit_scale_detached · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 6 claims |
| forbidden_extracted[4000.0] | ok | never `extracted` | [('ambiguous', 'capital_expenditure'), ('ambiguous', 'capital_expenditure'), ('needs_review', None), ('needs_review', None), ('needs_review', None), ('needs_review', None)] |

### GC-12 · unit_scale_detached · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 6 claims |
| forbidden_extracted[4000.0] | ok | never `extracted` | [('ambiguous', 'capital_expenditure'), ('ambiguous', 'capital_expenditure'), ('needs_review', None), ('needs_review', None), ('needs_review', None), ('needs_review', None)] |

### GC-13 · interleaved_detached_unit · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 30 claims |
| forbidden_extracted[335] | ok | never `extracted` | not emitted |
| expected[59413] | ok | status in ['extracted', 'ambiguous'], MW as on 31 March 2025 | ambiguous |
| expected[59078] | ok | status in ['extracted', 'ambiguous'], MW as on 31 March 2024 | ambiguous |

### GC-14 · partial_commissioning_and_project_list · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 17 claims |
| forbidden_extracted[23] | ok | never `extracted` | [('needs_review', 'capacity_commissioned')] |
| forbidden_extracted[20] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[56] | ok | never `extracted` | [('needs_review', None)] |
| forbidden_extracted[90] | ok | never `extracted` | [('needs_review', None)] |

### GC-15 · awarded_retrofit_capacity · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 4 claims |
| forbidden_extracted[2000] | ok | never `extracted` | [('ambiguous', 'capacity_target')] |
| forbidden_extracted[60940] | ok | never `extracted` | [('ambiguous', 'capacity_under_construction')] |
| forbidden_extracted[1340] | ok | never `extracted` | [('needs_review', None)] |

### GC-15 · awarded_retrofit_capacity · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 0 claims |
| forbidden_extracted[2000] | ok | never `extracted` | not emitted |
| forbidden_extracted[60940] | ok | never `extracted` | not emitted |
| forbidden_extracted[1340] | ok | never `extracted` | not emitted |

### GC-20 · clean_single_chunk_table · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 15 claims |
| expected[1.26] | ok | status in ['extracted'], percent 2015-16 | extracted |
| expected[1.59] | ok | status in ['extracted'], percent 2016-17 | extracted |
| expected[1.97] | ok | status in ['extracted'], percent 2017-18 | extracted |
| expected[129.68] | ok | status in ['ambiguous'], INR crore 2015-16 | ambiguous |

### GC-21 · split_header_and_data · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 44 claims |
| no_extracted_claims | ok | no extracted claim | none |
| forbidden_extracted[170037.37] | ok | never `extracted` | not emitted |
| forbidden_extracted[49749.28] | ok | never `extracted` | not emitted |
| forbidden_extracted[19649.41] | ok | never `extracted` | not emitted |
| forbidden_extracted[7000.0] | ok | never `extracted` | not emitted |
| forbidden_extracted[20.26] | ok | never `extracted` | not emitted |

### GC-21 · split_header_and_data · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 0 claims |
| no_extracted_claims | ok | no extracted claim | none |
| forbidden_extracted[170037.37] | ok | never `extracted` | not emitted |
| forbidden_extracted[49749.28] | ok | never `extracted` | not emitted |
| forbidden_extracted[19649.41] | ok | never `extracted` | not emitted |
| forbidden_extracted[7000.0] | ok | never `extracted` | not emitted |
| forbidden_extracted[20.26] | ok | never `extracted` | not emitted |

### GC-22 · reversed_table_text · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 17 claims |
| no_extracted_claims | ok | no extracted claim | none |

### GC-23 · stacked_multiline_cells · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 1 claims |
| no_extracted_claims | ok | no extracted claim | none |

### GC-24 · subsidiary_entity_columns_and_negatives · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 54 claims |
| no_extracted_claims | ok | no extracted claim | none |
| expected[-213.63] | ok | status in ['needs_review', 'ambiguous'], None As at 31 March 2019 | needs_review |

### GC-25 · flattened_number_run_with_glyph_currency · prose extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 4 claims |
| forbidden_extracted[34720.3] | ok | never `extracted` | not emitted |
| forbidden_extracted[33349.68] | ok | never `extracted` | not emitted |
| forbidden_extracted[1287.54] | ok | never `extracted` | not emitted |

### GC-25 · flattened_number_run_with_glyph_currency · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 4 claims |
| forbidden_extracted[34720.3] | ok | never `extracted` | not emitted |
| forbidden_extracted[33349.68] | ok | never `extracted` | not emitted |
| forbidden_extracted[1287.54] | ok | never `extracted` | not emitted |

### GC-26 · unresolved_entity_and_unstated_basis · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 6 claims |
| expected[189798.56] | ok | status in ['ambiguous', 'needs_review'], INR crore FY 2025–26 | ambiguous |

### GC-27 · table_label_lacks_parent · table extractor · **XFAIL (accepted gap: Known table-extractor gap: it currently marks these rows `extracted`; the section-row context is not modelled (Layer 1.5, accepted).)**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 10 claims |
| expected[94.02] | FAIL | status in ['ambiguous', 'needs_review'], percent FY 2017-18 | extracted |

### GC-30 · synthetic_other_company_historical · prose extractor · **PASS** · synthetic
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 1 claims |
| expected[500] | ok | status in ['extracted'], MW as on 31 March 2024 | extracted |

### GC-31 · synthetic_other_company_forward · prose extractor · **PASS** · synthetic
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 1 claims |
| forbidden_extracted[800] | ok | never `extracted` | [('ambiguous', 'capacity_target')] |

### GC-32 · synthetic_other_company_subsidiary · prose extractor · **PASS** · synthetic
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 1 claims |
| forbidden_extracted[120] | ok | never `extracted` | [('needs_review', 'capacity')] |

### GC-33 · synthetic_ntpc_as_third_party · prose extractor · **PASS** · synthetic
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 1 claims |
| forbidden_extracted[59413] | ok | never `extracted` | [('needs_review', 'installed_capacity')] |

### GC-34 · real_split_header_adjacent_data · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 2 claims |
| expected[3954.64] | ok | status in ['ambiguous', 'needs_review'], None FY 2022-23 | ambiguous |
| expected[3575.11] | ok | status in ['ambiguous', 'needs_review'], None FY 2021-22 | ambiguous |
| exact_claim_set | ok | [('ev_1fe8cca04346fecb5c8325e6', 'net_other_income', 3575.11, None, 'financial_year', 'FY 2021-22', None), ('ev_1fe8cca04346fecb5c8325e6', 'net_other_income', 3954.64, None, 'financial_year', 'FY 2022-23', None)] | [('ev_1fe8cca04346fecb5c8325e6', 'net_other_income', 3575.11, None, 'financial_year', 'FY 2021-22', None), ('ev_1fe8cca04346fecb5c8325e6', 'net_other_income', 3954.64, None, 'financial_year', 'FY 2022-23', None)] |

### GC-35 · real_table_continued_across_three_chunks · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 4 claims |
| expected[24067.09] | ok | status in ['ambiguous', 'needs_review'], None FY 2022-23 | ambiguous |
| expected[19325.33] | ok | status in ['ambiguous', 'needs_review'], None FY 2021-22 | ambiguous |
| expected[9979.23] | ok | status in ['ambiguous', 'needs_review'], None FY 2022-23 | ambiguous |
| expected[8216.54] | ok | status in ['ambiguous', 'needs_review'], None FY 2021-22 | ambiguous |
| exact_claim_set | ok | [('ev_53a534d42eb085990f1cda3f', 'profit_before_tax_and_regulatory_deferral_account_balances', 19325.33, None, 'financial_year', 'FY 2021-22', None), ('ev_53a534d42eb085990f1cda3f', 'profit_before_tax_and_regulatory_deferral_account_balances', 24067.09, None, 'financial_year', 'FY 2022-23', None), ('ev_c9f1d452749e43a50e184ce9', 'total_finance_costs', 8216.54, None, 'financial_year', 'FY 2021-22', None), ('ev_c9f1d452749e43a50e184ce9', 'total_finance_costs', 9979.23, None, 'financial_year', 'FY 2022-23', None)] | [('ev_53a534d42eb085990f1cda3f', 'profit_before_tax_and_regulatory_deferral_account_balances', 19325.33, None, 'financial_year', 'FY 2021-22', None), ('ev_53a534d42eb085990f1cda3f', 'profit_before_tax_and_regulatory_deferral_account_balances', 24067.09, None, 'financial_year', 'FY 2022-23', None), ('ev_c9f1d452749e43a50e184ce9', 'total_finance_costs', 8216.54, None, 'financial_year', 'FY 2021-22', None), ('ev_c9f1d452749e43a50e184ce9', 'total_finance_costs', 9979.23, None, 'financial_year', 'FY 2022-23', None)] |

### GC-36 · synthetic_chunks_ordered_by_page · table extractor · **PASS** · synthetic
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 4 claims |
| expected[500] | ok | status in ['extracted'], MW As at 31 March 2025 | extracted |
| expected[450] | ok | status in ['extracted'], MW As at 31 March 2024 | extracted |
| expected[120] | ok | status in ['extracted'], MW As at 31 March 2025 | extracted |
| expected[80] | ok | status in ['extracted'], MW As at 31 March 2024 | extracted |
| exact_claim_set | ok | [('ev_6e165b4411f13a463c49af1e', 'renewable_capacity', 80, 'MW', 'as_of', 'As at 31 March 2024', '2024-03-31'), ('ev_6e165b4411f13a463c49af1e', 'renewable_capacity', 120, 'MW', 'as_of', 'As at 31 March 2025', '2025-03-31'), ('ev_e62aa42947434e3d66189f10', 'installed_capacity', 450, 'MW', 'as_of', 'As at 31 March 2024', '2024-03-31'), ('ev_e62aa42947434e3d66189f10', 'installed_capacity', 500, 'MW', 'as_of', 'As at 31 March 2025', '2025-03-31')] | [('ev_6e165b4411f13a463c49af1e', 'renewable_capacity', 80, 'MW', 'as_of', 'As at 31 March 2024', '2024-03-31'), ('ev_6e165b4411f13a463c49af1e', 'renewable_capacity', 120, 'MW', 'as_of', 'As at 31 March 2025', '2025-03-31'), ('ev_e62aa42947434e3d66189f10', 'installed_capacity', 450, 'MW', 'as_of', 'As at 31 March 2024', '2024-03-31'), ('ev_e62aa42947434e3d66189f10', 'installed_capacity', 500, 'MW', 'as_of', 'As at 31 March 2025', '2025-03-31')] |

### GC-37 · real_same_width_different_table_boundary · table extractor · **PASS**
| Check | Result | Expected | Actual |
|---|---|---|---|
| schema_unverified_provenance | ok | valid, unverified, provenance preserved | 15 claims |
| expected[3.67] | ok | status in ['needs_review'], None None | needs_review |
| expected[8.64] | ok | status in ['needs_review'], None None | needs_review |
| expected[55.73] | ok | status in ['needs_review'], None None | needs_review |
| expected[30.43] | ok | status in ['needs_review'], None None | needs_review |
| expected[98.47] | ok | status in ['needs_review'], None None | needs_review |
| exact_claim_set | ok | [('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 3.67, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 8.64, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 30.43, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 55.73, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 98.47, None, 'unknown', None, None)] | [('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 3.67, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 8.64, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 30.43, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 55.73, None, 'unknown', None, None), ('ev_a346a8aab8eb8a1acea574e1', 'projects_in_progress', 98.47, None, 'unknown', None, None)] |


34/35 case x extractor runs passed
