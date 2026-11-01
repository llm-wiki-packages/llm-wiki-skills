# channel-blackboard — after enabling

1. Make the credential, naming the institution's Blackboard host:
   `{{@brain-cli-ops}} credentials set blackboard kind=dir login=browser host=<host>`.
   A second institution is a second credential under its own name.
2. Sign in, attended: `/channel-blackboard login https://<host>`. The
   credential store never syncs, so every machine that harvests signs in once.
3. Check it: `/channel-blackboard courses` lists the memberships.
