# Kubernetes Pods - Basics

## What is a Pod?
- Smallest deployable unit in Kubernetes
- A pod is a group of one or more containers with shared storage and network resources
- Pods are ephemeral - they are not designed to run forever
- Each pod gets its own IP address

## Pod Lifecycle
- Pending: Pod accepted but containers not yet running
- Running: At least one container is running
- Succeeded: All containers terminated successfully
- Failed: At least one container terminated with failure
- Unknown: State cannot be determined

## Creating Pods

### Imperative way
```bash
kubectl run nginx --image=nginx --port=80
```

### Declarative way (YAML)
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
  labels:
    app: nginx
spec:
  containers:
  - name: nginx
    image: nginx:1.25
    ports:
    - containerPort: 80
```

Apply with:
```bash
kubectl apply -f pod.yaml
```

## Key Commands
- `kubectl get pods` - List all pods
- `kubectl get pods -o wide` - List pods with more details (IP, node)
- `kubectl describe pod <name>` - Detailed info about a pod
- `kubectl logs <pod-name>` - View pod logs
- `kubectl logs <pod-name> -c <container>` - Logs for specific container in multi-container pod
- `kubectl exec -it <pod-name> -- /bin/bash` - Shell into a pod
- `kubectl delete pod <name>` - Delete a pod

## Multi-Container Pods
- Sidecar pattern: Helper container that enhances the main container (e.g., log shipper)
- Ambassador pattern: Proxy container that simplifies external communication
- Adapter pattern: Container that standardizes output from the main container

## Important for CKA
- Know how to create pods from command line quickly (imperative)
- Know how to write pod YAML from scratch
- Understand pod lifecycle phases
- Know how to troubleshoot pods (describe, logs, exec)
- Multi-container pod patterns are tested
