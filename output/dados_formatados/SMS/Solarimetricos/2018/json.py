import json

station_data = {
    key: {
        "SD": [
            "pir_thermpil", "pir_thermpil", "pir_thermpil", "pir_thermpil",
            "pir_shdtrker\npir_shdring", "pir_shdtrker\npir_shdring",
            "pir_shdtrker\npir_shdring", "pir_shdtrker\npir_shdring",
            "par_photodio", "par_photodio", "par_photodio", "par_photodio",
            "lux_photodio", "lux_photodio", "lux_photodio", "lux_photodio",
            "phl_thermpil", "phl_thermpil", "phl_thermpil", "phl_thermpil",
            "prg_shdtrker", "prg_shdtrker", "prg_shdtrker", "prg_shdtrker",
            "prg_shdtrker", "prg_shdtrker", "prg_shdtrker", "prg_shdtrker",
            "tcp_sensor", "tcp_sensor", "tcp_sensor", "tcp_sensor", "tcp_sensor"
        ],
        "MD": [
            "tmo_aspirat", "hgr_aspirat", "bar_atmosph", "plv_tipbuk",
            "anm_propel\nanm_sonic", "anm_propel\nanm_sonic",
            "anm_propel\nanm_sonic", "anm_propel\nanm_sonic"
        ],
        "WD": [
            "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic",
            "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic",
            "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic",
            "anm_propel\nanm_sonic", "tmo_ventil", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic",
            "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic", "anm_propel\nanm_sonic",
            "tmo_ventil"
        ],
        "CD": [
            "sky_camera\nsky_mirror", "sky_camera\nsky_mirror",
            "sky_camera\nsky_mirror", "sky_camera\nsky_mirror",
            "sky_camera\nsky_mirror"
        ]
    } for key in ['sbr', 'spk', 'pma', 'sjc', 'ptr', 'mcl', 'leb', 'scr', 'cpa', 'cts', 'rlm', 'ctb',
                  'mds', 'sms', 'tma', 'chp', 'fln', 'brb', 'cgr', 'tri', 'joi', 'ube', 'orn', 'tlg',
                  'slz', 'bjl', 'stm', 'nat', 'cms', 'cba', 'cai', 'opo']
}

with open("station_data.json", "w") as json_file:
    json.dump(station_data, json_file, indent=4)
