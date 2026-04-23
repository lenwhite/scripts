if [[ $(pwd) != *"/projects/instawork"* ]]; then
    echo "You must be in the instawork project directory to run this command"
    return
fi

# check if watchexec is installed
if ! docker compose exec backend which watchexec &>/dev/null; then
    echo "Installing watchexec"
    docker compose exec backend wget "https://github.com/watchexec/watchexec/releases/download/v2.1.1/watchexec-2.1.1-aarch64-unknown-linux-gnu.tar.xz" -O /tmp/watchexec.tar.xz
    docker compose exec backend tar xf /tmp/watchexec.tar.xz -C /tmp
    docker compose exec backend mv /tmp/watchexec-2.1.1-aarch64-unknown-linux-gnu/watchexec /home/app/.local/bin
    docker compose exec backend rm -rf /tmp/watchexec-2.1.1-aarch64-unknown-linux-gnu /tmp/watchexec.tar.xz
fi

first_run_command="./scripts/bin/pytest.sh -n0 -x $@"
echo $first_run_command
docker compose exec backend bash -c "$first_run_command"
command="watchexec --exts .py -- ./scripts/bin/pytest.sh -n0 -x --failed-first --reuse-db --no-migrations $@"
echo $command
docker compose exec backend bash -c "$command"
