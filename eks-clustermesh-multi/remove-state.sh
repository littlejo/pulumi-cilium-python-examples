while pulumi stack --show-urns | grep cilium | grep URN > /tmp/urn
do
        state=$(head -1 /tmp/urn | awk '{print $NF}')
        echo "pulumi state delete --target-dependents '$state'" | bash
done
