export CARLA_ROOT=/home/ros/e2etransfuser/transfuser_pami/carla
export WORK_DIR=/home/ros/e2etransfuser/transfuser_pami

export CARLA_SERVER=${CARLA_ROOT}/CarlaUE4.sh
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
export PYTHONPATH=$PYTHONPATH:$CARLA_ROOT/PythonAPI/carla/dist/carla-0.9.10-py3.7-linux-x86_64.egg
export SCENARIO_RUNNER_ROOT=${WORK_DIR}/scenario_runner
export LEADERBOARD_ROOT=${WORK_DIR}/leaderboard
export PYTHONPATH="${CARLA_ROOT}/PythonAPI/carla/":"${SCENARIO_RUNNER_ROOT}":"${LEADERBOARD_ROOT}":${PYTHONPATH}

export SCENARIOS=${WORK_DIR}/leaderboard/data/longest6/eval_scenarios.json
export ROUTES=${WORK_DIR}/leaderboard/data/longest6/longest6.xml
export REPETITIONS=1
export CHALLENGE_TRACK_CODENAME=SENSORS
export SAVE_PATH=data0/transfuser_PAMI_Adv/
export CHECKPOINT_ENDPOINT=${SAVE_PATH}/eval_result.json
export TEAM_AGENT=${WORK_DIR}/team_code_transfuser/submission_agent.py
#export TEAM_CONFIG=/media/ros/hdd2/Porjects/e2etransfuser/transfuser_pami/log/transfuser
export TEAM_CONFIG=/home/ros/e2etransfuser/transfuser_pami/model_ckpt/models_2022/transfuser
export DEBUG_CHALLENGE=0
export RESUME=1
export DATAGEN=0

python3 ${LEADERBOARD_ROOT}/leaderboard/leaderboard_evaluator_local.py \
--scenarios=${SCENARIOS}  \
--routes=${ROUTES} \
--repetitions=${REPETITIONS} \
--track=${CHALLENGE_TRACK_CODENAME} \
--checkpoint=${CHECKPOINT_ENDPOINT} \
--agent=${TEAM_AGENT} \
--agent-config=${TEAM_CONFIG} \
--debug=${DEBUG_CHALLENGE} \
--resume=${RESUME}
